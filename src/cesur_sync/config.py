import os

from dotenv import load_dotenv

load_dotenv()

CESUR_BASE_URL = os.environ.get(
    "CESUR_BASE_URL", "https://campusonline2026.cesurformacion.com"
)
CESUR_TIMEZONE = os.environ.get("CESUR_TIMEZONE", "Europe/Madrid")
PROFILE_DIR = os.environ.get("PROFILE_DIR", "./browser_profile")
OUTPUT_FILE = os.environ.get("OUTPUT_FILE", "./assignments.json")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC")

GOOGLE_CREDENTIALS_FILE = os.environ.get(
    "GOOGLE_CREDENTIALS_FILE", "./credentials.json"
)
GOOGLE_TOKEN_FILE = os.environ.get("GOOGLE_TOKEN_FILE", "./token.json")
SYNC_STATE_FILE = os.environ.get("SYNC_STATE_FILE", "./sync_state.json")
GOOGLE_TASKLIST_NAME = os.environ.get("GOOGLE_TASKLIST_NAME", "")
GOOGLE_CALENDAR_NAME = os.environ.get("GOOGLE_CALENDAR_NAME", "Cesur")
# Minutos antes de cada tutoría para el aviso; "none" = sin aviso; vacío = avisos por defecto del calendario
TUTORIAL_REMINDER_MINUTES = os.environ.get("TUTORIAL_REMINDER_MINUTES", "60")
FORMAT_RULES_FILE = os.environ.get("FORMAT_RULES_FILE", "./format_rules.toml")
