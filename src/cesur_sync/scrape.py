import json
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import dateparser
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, sync_playwright

from cesur_sync.config import (
    CESUR_BASE_URL,
    CESUR_TIMEZONE,
    NTFY_TOPIC,
    OUTPUT_FILE,
    PROFILE_DIR,
)


def notify(message: str):
    print(f"[notify] {message}")
    if NTFY_TOPIC:
        try:
            requests.post(
                f"https://ntfy.sh/{NTFY_TOPIC}",
                data=message.encode("utf-8"),
                timeout=10,
            )
        except requests.RequestException as e:
            print(f"[notify] ha fallado al enviar la alerta: {e}")


def write_output(assignments: list[dict]):
    payload = {
        "generated_at": datetime.now(ZoneInfo(CESUR_TIMEZONE)).isoformat(),
        "count": len(assignments),
        "assignments": assignments,
    }
    Path(OUTPUT_FILE).write_text(json.dumps(payload, indent=2, ensure_ascii=False))


def ensure_logged_in(page: Page) -> bool:
    page.goto(f"{CESUR_BASE_URL}/my/", wait_until="networkidle")

    if "login" not in page.url:
        return True  # Ya iniciado

    print("Intentando autenticación silenciosa...")
    try:
        page.click("text=Office 365", timeout=8000)
        page.wait_for_load_state("networkidle", timeout=15000)
    except PlaywrightError as e:
        print(f"Error al pulsar el botón de SSO: {e}")
        return False

    page.goto(f"{CESUR_BASE_URL}/my/", wait_until="networkidle")

    if "login" in page.url:
        # No hay sesión OAuth, necesita re-autenticación manual
        return False

    print("SSO completado")
    return True


def get_courses(page: Page) -> list[dict]:
    page.goto(f"{CESUR_BASE_URL}/my/courses.php", wait_until="networkidle")
    soup = BeautifulSoup(page.content(), "html.parser")

    courses = []
    seen_ids = set()
    for link in soup.select('a[href*="course/view.php?id="]'):
        href = link.get("href", "")
        m = re.search(r"id=(\d+)", href)
        if not m:
            continue
        course_id = m.group(1)
        if course_id in seen_ids:
            continue
        name = link.get_text(strip=True)
        if not name:
            continue
        seen_ids.add(course_id)
        courses.append({"id": course_id, "name": name})

    return courses


def get_assignments_for_course(page, course_id: str, course_name: str) -> list[dict]:
    url = f"{CESUR_BASE_URL}/mod/assign/index.php?id={course_id}"
    page.goto(url, wait_until="networkidle")
    soup = BeautifulSoup(page.content(), "html.parser")

    table = soup.find("table")
    if not table:
        return []

    assignments = []
    headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]

    def col_index(*keywords):
        for i, h in enumerate(headers):
            if any(k in h for k in keywords):
                return i
        return None

    name_idx = col_index("nombre", "assignment")
    due_idx = col_index("fecha de entrega", "due date")

    if name_idx is None or due_idx is None:
        print(
            f"  [!] Formato de tabla inesperado en {course_name} ({course_id}), omitiendo."
        )
        return []

    for row in table.find_all("tr")[1:]:
        cells = row.find_all("td")
        if len(cells) <= max(name_idx, due_idx):
            continue

        name_cell = cells[name_idx]
        link = name_cell.find("a")
        name_text = (
            link.get_text(strip=True) if link else name_cell.get_text(strip=True)
        )
        href = link.get("href", "") if link else ""
        cmid_match = re.search(r"id=(\d+)", href)
        cmid = cmid_match.group(1) if cmid_match else None

        due_text = cells[due_idx].get_text(strip=True)
        if not due_text or due_text == "-":
            continue  # no hay fecha de límite

        due_dt = dateparser.parse(
            due_text,
            languages=["es"],
            settings={"TIMEZONE": CESUR_TIMEZONE, "RETURN_AS_TIMEZONE_AWARE": True},
        )
        if not due_dt:
            print(
                f"  [!] No se pudo parsear la fecha de entrega '{due_text}' para '{name_text}', omitiendo."
            )
            continue

        assignments.append(
            {
                "key": f"assign-{cmid or name_text}",
                "course": course_name,
                "name": name_text,
                "due": due_dt.isoformat(),
                "url": f"{CESUR_BASE_URL}/mod/assign/view.php?id={cmid}"
                if cmid
                else url,
            }
        )

    return assignments


def main():
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(PROFILE_DIR, headless=True)
        page = context.pages[0] if context.pages else context.new_page()

        if not ensure_logged_in(page):
            notify(
                "Cesur sync: Se han expirado las sesiones de Cesur y Microsoft. "
                "Por favor, ejecutar nuevamente cesur-login y copia el perfil actualizado al contenedor."
            )
            context.close()
            sys.exit(1)

        courses = get_courses(page)
        print(f"Encontradas {len(courses)} asignaturas")

        all_assignments = []
        for course in courses:
            print(f"Escaneando: {course['name']}")
            assignments = get_assignments_for_course(page, course["id"], course["name"])
            all_assignments.extend(assignments)

        context.close()

    print(f"\nEncontradas {len(all_assignments)} tareas con fecha de entrega")

    write_output(all_assignments)
    print(f"Escrito a {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
