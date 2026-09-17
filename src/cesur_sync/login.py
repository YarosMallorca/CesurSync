import sys

from playwright.sync_api import sync_playwright

from cesur_sync.config import CESUR_BASE_URL, PROFILE_DIR


def main():
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            PROFILE_DIR,
            headless=False,
            viewport={"width": 1280, "height": 900},
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(f"{CESUR_BASE_URL}/login/index.php")

        print("\n--- Una ventana del navegador ha sido abierta ---")
        print("1. Pulsa el botón 'Office 365'")
        print("2. Inicia sesión con tu cuenta de Microsoft")
        print("3. Completa 2FA si es necesario (SMS, app, etc.)")
        print(
            "4. (MUY IMPORTANTE) Si pregunta si quieres mantener la sesión iniciada, acepta"
        )
        print('5. Espera hasta que llegues al dashboard de "Mis Cursos"')
        input(
            "\nUna vez en el dashboard, pulsa Enter aquí para guardar la sesión y cerrar el navegador..."
        )

        page.goto(f"{CESUR_BASE_URL}/my/")
        if "login" in page.url:
            print(
                "\n[!] Parece que estás en la página de login, no se ha podido capturar la sesión correctamente."
            )
            sys.exit(1)

        print(f"\nSesion capturada, guardada en: {PROFILE_DIR}")
        print(
            "Copia esta carpeta al contenedor/VM donde vayas a ejecutar cesur-sync para que pueda usar la sesión guardada."
        )

        context.close()


if __name__ == "__main__":
    main()
