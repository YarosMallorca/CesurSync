import json
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import dateparser
from bs4 import BeautifulSoup
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, sync_playwright

from cesur_sync.config import (
    CESUR_BASE_URL,
    CESUR_TIMEZONE,
    OUTPUT_FILE,
    PROFILE_DIR,
)
from cesur_sync.notify import notify


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


def get_tutorials(page: Page) -> list[dict]:
    page.goto(f"{CESUR_BASE_URL}/local/tutorials/index.php", wait_until="networkidle")

    sesskey = page.evaluate("() => M.cfg.sesskey")
    contextid = page.evaluate("() => M.cfg.contextid")

    payload = [
        {
            "index": 0,
            "methodname": "core_get_fragment",
            "args": {
                "component": "local_tutorials",
                "callback": "mytutorials_list",
                "contextid": contextid,
                "args": [
                    {"name": "courseid", "value": 0},
                    {"name": "typefilter", "value": ""},
                    {"name": "search", "value": ""},
                    {"name": "sortkey", "value": ""},
                    {"name": "sortorder", "value": ""},
                    {"name": "statefilter", "value": ""},
                    {"name": "page", "value": 0},
                    {"name": "perpage", "value": 100},
                ],
            },
        }
    ]

    result = page.evaluate(
        """
        async ({ path, payload }) => {
            const resp = await fetch(path, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
                credentials: "same-origin",
            });
            return await resp.json();
        }
        """,
        {
            "path": f"/lib/ajax/service.php?sesskey={sesskey}&info=core_get_fragment",
            "payload": payload,
        },
    )

    if not isinstance(result, list) or result[0].get("error"):
        print(f"  [!] Tutorials fragment call returned an error: {result}")
        return []

    html = result[0]["data"]["html"]
    soup = BeautifulSoup(html, "html.parser")

    table = soup.find("table")
    if not table:
        print("  [!] No <table> found inside the tutorials fragment HTML.")
        return []

    headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]

    def col_index(*keywords):
        for i, h in enumerate(headers):
            if any(k in h for k in keywords):
                return i
        return None

    title_idx = col_index("título", "title")
    when_idx = col_index("fecha y hora", "fecha", "date")
    type_idx = col_index("tipo", "type")
    course_idx = col_index("curso", "course")
    tutor_idx = col_index("tutor")
    state_idx = col_index("estado", "state")

    tutorials = []
    body_rows = (
        table.find("tbody").find_all("tr")
        if table.find("tbody")
        else table.find_all("tr")[1:]
    )

    def cell_text(cells, idx: int | None):
        if idx is None or idx >= len(cells):
            return None
        return cells[idx].get_text(" ", strip=True)

    for row in body_rows:
        cells = row.find_all("td")
        if not cells:
            continue

        title = cell_text(cells, title_idx)
        when_text = cell_text(cells, when_idx)
        when_start, when_end = parse_tutorial_when(when_text)

        link = (
            cells[title_idx].find("a")
            if title_idx is not None and title_idx < len(cells)
            else None
        )
        href = link.get("href") if link else None

        tutorials.append(
            {
                "key": f"tutorial-{href or title}",
                "title": title,
                "when_raw": when_text,
                "when_start": when_start,
                "when_end": when_end,
                "type": cell_text(cells, type_idx),
                "course": cell_text(cells, course_idx),
                "tutor": cell_text(cells, tutor_idx),
                "state": cell_text(cells, state_idx),
                "url": href,
            }
        )

    return tutorials


def parse_cesur_date(text: str):
    return dateparser.parse(
        text,
        languages=["es"],
        settings={"TIMEZONE": CESUR_TIMEZONE, "RETURN_AS_TIMEZONE_AWARE": True},
    )


def parse_tutorial_when(when_raw: str | None):
    if not when_raw:
        return None, None

    parts = re.split(r"\s*[–—-]\s*", when_raw)
    if len(parts) != 2:
        dt = parse_cesur_date(when_raw)
        return (dt.isoformat() if dt else None), None

    start_text, end_text = parts[0].strip(), parts[1].strip()
    start_dt = parse_cesur_date(start_text)
    if not start_dt:
        return None, None

    end_match = re.match(r"^(\d{1,2}):(\d{2})$", end_text)
    if end_match:
        end_dt = start_dt.replace(
            hour=int(end_match.group(1)), minute=int(end_match.group(2))
        )
    else:
        end_dt = parse_cesur_date(end_text)

    return start_dt.isoformat(), (end_dt.isoformat() if end_dt else None)


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

        due_dt = parse_cesur_date(due_text)
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


def write_output(assignments: list[dict], tutorials: list[dict]):
    payload = {
        "generated_at": datetime.now(ZoneInfo(CESUR_TIMEZONE)).isoformat(),
        "assignments": assignments,
        "tutorials": tutorials,
    }
    Path(OUTPUT_FILE).write_text(json.dumps(payload, indent=2, ensure_ascii=False))


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

        tutorials = get_tutorials(page)
        print(f"Encontradas {len(tutorials)} tutorías")

        pending_tutorials = [t for t in tutorials if t["state"] == "Programada"]

        context.close()

    print(f"\nEncontradas {len(all_assignments)} tareas con fecha de entrega")
    print(f"Encontradas {len(pending_tutorials)} tutorías programadas")

    write_output(all_assignments, pending_tutorials)
    print(f"Escrito a {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
