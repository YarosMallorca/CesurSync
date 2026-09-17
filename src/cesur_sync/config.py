import os

CESUR_BASE_URL = os.environ.get(
    "CESUR_BASE_URL", "https://campusonline.cesurformacion.com"
)
CESUR_TIMEZONE = os.environ.get("CESUR_TIMEZONE", "Europe/Madrid")
PROFILE_DIR = os.environ.get("PROFILE_DIR", "./browser_profile")
OUTPUT_FILE = os.environ.get("OUTPUT_FILE", "./assignments.json")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC")
