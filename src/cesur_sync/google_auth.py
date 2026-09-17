from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from cesur_sync.config import GOOGLE_CREDENTIALS_FILE, GOOGLE_TOKEN_FILE

SCOPES = [
    "https://www.googleapis.com/auth/tasks",
    # Solo permite gestionar calendarios creados por esta app, no el calendario principal
    "https://www.googleapis.com/auth/calendar.app.created",
]


def save_credentials(creds: Credentials):
    path = Path(GOOGLE_TOKEN_FILE)
    path.write_text(creds.to_json())
    path.chmod(0o600)


def load_credentials() -> Credentials | None:
    """Devuelve credenciales válidas, o None si hay que volver a ejecutar cesur-google-login."""
    if not Path(GOOGLE_TOKEN_FILE).exists():
        return None

    creds = Credentials.from_authorized_user_file(GOOGLE_TOKEN_FILE, SCOPES)
    if creds.valid:
        return creds

    try:
        creds.refresh(Request())
    except RefreshError as e:
        print(f"Error al refrescar el token de Google: {e}")
        return None

    save_credentials(creds)
    return creds


def main():
    flow = InstalledAppFlow.from_client_secrets_file(GOOGLE_CREDENTIALS_FILE, SCOPES)
    # prompt=consent garantiza que Google devuelva un refresh token
    creds = flow.run_local_server(port=0, prompt="consent")
    save_credentials(creds)

    print(f"\nToken de Google guardado en: {GOOGLE_TOKEN_FILE}")
    print(
        "Copia este archivo al contenedor/VM donde vayas a ejecutar cesur-sync-google."
    )


if __name__ == "__main__":
    main()
