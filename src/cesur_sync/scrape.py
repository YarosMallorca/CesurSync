import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, sync_playwright

from cesur_sync.config import (
    CESUR_BASE_URL,
    CESUR_TIMEZONE,
    OUTPUT_FILE,
    PROFILE_DIR,
)
from cesur_sync.notify import notify
from cesur_sync.parsing import parse_assignments, parse_courses, parse_tutorials


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
    return parse_courses(page.content())


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

    if not isinstance(result, list) or not result or result[0].get("error"):
        print(f"  [!] Tutorials fragment call returned an error: {result}")
        return []

    return parse_tutorials(result[0]["data"]["html"])


def get_assignments_for_course(page, course_id: str, course_name: str) -> list[dict]:
    url = f"{CESUR_BASE_URL}/mod/assign/index.php?id={course_id}"
    page.goto(url, wait_until="networkidle")
    return parse_assignments(page.content(), course_id, course_name, url)


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
