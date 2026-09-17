import requests

from cesur_sync.config import NTFY_TOPIC


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
