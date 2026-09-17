import argparse
import hashlib
import json
import re
import sys
import tomllib
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from cesur_sync.config import (
    CESUR_TIMEZONE,
    FORMAT_RULES_FILE,
    GOOGLE_CALENDAR_NAME,
    GOOGLE_TASKLIST_NAME,
    OUTPUT_FILE,
    SYNC_STATE_FILE,
)
from cesur_sync.formatting import Formatter
from cesur_sync.google_auth import load_credentials
from cesur_sync.notify import notify

KEY_MARKER_RE = re.compile(r"\[cesur:(.+?)\]")
DEFAULT_TUTORIAL_DURATION = timedelta(hours=1)


def load_state() -> dict:
    path = Path(SYNC_STATE_FILE)
    return json.loads(path.read_text()) if path.exists() else {}


def save_state(state: dict):
    Path(SYNC_STATE_FILE).write_text(json.dumps(state, indent=2))


def find_tasklist(tasks) -> str | None:
    if not GOOGLE_TASKLIST_NAME:
        return "@default"  # Alias de la API para la lista por defecto del usuario

    page_token = None
    while True:
        resp = tasks.tasklists().list(maxResults=100, pageToken=page_token).execute()
        for tasklist in resp.get("items", []):
            if tasklist["title"] == GOOGLE_TASKLIST_NAME:
                return tasklist["id"]
        page_token = resp.get("nextPageToken")
        if not page_token:
            return None


def ensure_calendar(cal, state: dict) -> str:
    if calendar_id := state.get("calendar_id"):
        try:
            cal.calendars().get(calendarId=calendar_id).execute()
            return calendar_id
        except HttpError as e:
            if e.status_code != 404:
                raise
            print("El calendario guardado ya no existe, creando uno nuevo.")

    created = (
        cal.calendars()
        .insert(body={"summary": GOOGLE_CALENDAR_NAME, "timeZone": CESUR_TIMEZONE})
        .execute()
    )
    state["calendar_id"] = created["id"]
    save_state(state)
    return created["id"]


def list_existing_tasks(tasks, list_id: str) -> dict[str, dict]:
    """Tareas creadas por este sync, indexadas por su key. Incluye completadas y borradas
    para no volver a crear las que el usuario ya ha completado o eliminado."""
    existing = {}
    page_token = None
    while True:
        resp = (
            tasks.tasks()
            .list(
                tasklist=list_id,
                maxResults=100,
                showCompleted=True,
                showHidden=True,
                showDeleted=True,
                pageToken=page_token,
            )
            .execute()
        )
        for task in resp.get("items", []):
            if m := KEY_MARKER_RE.search(task.get("notes", "")):
                existing[m.group(1)] = task
        page_token = resp.get("nextPageToken")
        if not page_token:
            return existing


def task_title(a: dict, fmt: Formatter) -> str:
    return fmt.apply(f"{a['name']} ({a['course']})", "tasks")


def event_title(t: dict, fmt: Formatter) -> str:
    return fmt.apply(t["title"], "events")


def sync_assignments(tasks, list_id: str, assignments: list[dict], fmt: Formatter):
    existing = list_existing_tasks(tasks, list_id)
    created = updated = 0

    for a in assignments:
        due = datetime.fromisoformat(a["due"]).astimezone(ZoneInfo(CESUR_TIMEZONE))
        body = {
            "title": task_title(a, fmt),
            "notes": f"{a['url']}\n[cesur:{a['key']}]",
            # Tasks ignora la hora; se envía la fecha local a medianoche UTC para que
            # no se desplace de día al convertir a UTC
            "due": due.strftime("%Y-%m-%dT00:00:00.000Z"),
        }

        task = existing.get(a["key"])
        if task is None:
            tasks.tasks().insert(tasklist=list_id, body=body).execute()
            created += 1
        elif any(task.get(field) != value for field, value in body.items()):
            # Sin tocar "status", para no desmarcar tareas completadas
            tasks.tasks().patch(tasklist=list_id, task=task["id"], body=body).execute()
            updated += 1

    print(f"Tareas: {created} creadas, {updated} actualizadas")


def event_id(key: str) -> str:
    # Los IDs de Calendar solo admiten base32hex (a-v, 0-9); hex es un subconjunto
    return hashlib.sha1(key.encode()).hexdigest()


def list_existing_events(cal, calendar_id: str) -> dict[str, dict]:
    existing = {}
    page_token = None
    while True:
        resp = (
            cal.events()
            .list(calendarId=calendar_id, showDeleted=True, pageToken=page_token)
            .execute()
        )
        for event in resp.get("items", []):
            existing[event["id"]] = event
        page_token = resp.get("nextPageToken")
        if not page_token:
            return existing


def event_differs(event: dict, body: dict) -> bool:
    if event.get("status") != "confirmed":
        return True
    for field in ("summary", "description"):
        if event.get(field, "") != body[field]:
            return True
    for field in ("start", "end"):
        current = event.get(field, {}).get("dateTime")
        if not current or datetime.fromisoformat(current) != datetime.fromisoformat(
            body[field]["dateTime"]
        ):
            return True
    return False


def sync_tutorials(cal, calendar_id: str, tutorials: list[dict], fmt: Formatter):
    existing = list_existing_events(cal, calendar_id)
    created = updated = deleted = 0
    wanted_ids = set()

    for t in tutorials:
        if not t.get("when_start"):
            print(f"  [!] Tutoría '{t['title']}' sin fecha, omitiendo.")
            continue

        start = datetime.fromisoformat(t["when_start"])
        end = (
            datetime.fromisoformat(t["when_end"])
            if t.get("when_end")
            else start + DEFAULT_TUTORIAL_DURATION
        )
        description = "\n".join(
            filter(None, [t.get("type"), t.get("tutor"), t.get("url")])
        )
        body = {
            "id": event_id(t["key"]),
            "summary": event_title(t, fmt),
            "description": description,
            "start": {"dateTime": start.isoformat(), "timeZone": CESUR_TIMEZONE},
            "end": {"dateTime": end.isoformat(), "timeZone": CESUR_TIMEZONE},
            "status": "confirmed",
            "extendedProperties": {"private": {"cesurKey": t["key"]}},
        }
        wanted_ids.add(body["id"])

        event = existing.get(body["id"])
        if event is None:
            cal.events().insert(calendarId=calendar_id, body=body).execute()
            created += 1
        elif event_differs(event, body):
            # También restaura eventos cancelados si la tutoría vuelve a estar programada
            cal.events().patch(
                calendarId=calendar_id, eventId=body["id"], body=body
            ).execute()
            updated += 1

    # Si el scrape no devolvió tutorías puede ser un fallo transitorio: no borrar nada
    if tutorials:
        now = datetime.now(ZoneInfo(CESUR_TIMEZONE))
        for event in existing.values():
            if event["id"] in wanted_ids or event.get("status") == "cancelled":
                continue
            end = event.get("end", {}).get("dateTime")
            if end and datetime.fromisoformat(end) > now:
                cal.events().delete(
                    calendarId=calendar_id, eventId=event["id"]
                ).execute()
                deleted += 1

    print(f"Tutorías: {created} creadas, {updated} actualizadas, {deleted} eliminadas")


def preview(data: dict, fmt: Formatter):
    print("Tareas:")
    for a in data["assignments"]:
        print(f"  {a['name']} ({a['course']})\n    → {task_title(a, fmt)}")
    print("\nTutorías:")
    for t in data["tutorials"]:
        print(f"  {t['title']}\n    → {event_title(t, fmt)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--preview",
        action="store_true",
        help="muestra cómo quedan los títulos con las reglas de formato, sin tocar Google",
    )
    args = parser.parse_args()

    try:
        fmt = Formatter.from_file(FORMAT_RULES_FILE)
    except (ValueError, tomllib.TOMLDecodeError) as e:
        notify(f"Cesur sync: error en las reglas de formato: {e}")
        sys.exit(1)

    data = json.loads(Path(OUTPUT_FILE).read_text())

    if args.preview:
        preview(data, fmt)
        return

    creds = load_credentials()
    if creds is None:
        notify(
            "Cesur sync: El token de Google ha expirado o no existe. "
            "Por favor, ejecutar nuevamente cesur-google-login y copia token.json al contenedor."
        )
        sys.exit(1)

    state = load_state()

    tasks = build("tasks", "v1", credentials=creds, cache_discovery=False)
    cal = build("calendar", "v3", credentials=creds, cache_discovery=False)

    tasklist_id = find_tasklist(tasks)
    if tasklist_id is None:
        print(
            f"[!] No existe la lista de tareas '{GOOGLE_TASKLIST_NAME}' en Google Tasks."
        )
        sys.exit(1)

    sync_assignments(tasks, tasklist_id, data["assignments"], fmt)
    sync_tutorials(cal, ensure_calendar(cal, state), data["tutorials"], fmt)


if __name__ == "__main__":
    main()
