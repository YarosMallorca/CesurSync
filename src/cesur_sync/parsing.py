import re

import dateparser
from bs4 import BeautifulSoup

from cesur_sync.config import CESUR_BASE_URL, CESUR_TIMEZONE


def _column_index(headers: list[str], *keywords) -> int | None:
    for i, h in enumerate(headers):
        if any(k in h for k in keywords):
            return i
    return None


def parse_courses(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")

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


def parse_tutorials(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")

    table = soup.find("table")
    if not table:
        print("  [!] No <table> found inside the tutorials fragment HTML.")
        return []

    headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]

    title_idx = _column_index(headers, "título", "title")
    when_idx = _column_index(headers, "fecha y hora", "fecha", "date")
    type_idx = _column_index(headers, "tipo", "type")
    course_idx = _column_index(headers, "curso", "course")
    tutor_idx = _column_index(headers, "tutor")
    state_idx = _column_index(headers, "estado", "state")

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


def parse_assignments(
    html: str, course_id: str, course_name: str, index_url: str
) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")

    table = soup.find("table")
    if not table:
        return []

    assignments = []
    headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]

    name_idx = _column_index(headers, "nombre", "assignment")
    due_idx = _column_index(headers, "fecha de entrega", "due date")

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
                else index_url,
            }
        )

    return assignments
