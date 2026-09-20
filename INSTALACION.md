# Instalación y uso

Guía completa de CesurSync: desde el primer `mise run setup` hasta dejarlo
sincronizando solo cada hora. Para saber qué hace el proyecto, vuelve al
[README](README.md).

## Requisitos

- **Python 3.12 o superior** y [uv](https://docs.astral.sh/uv/) para instalar el
  proyecto. Con [mise](https://mise.jdx.dev) instalado, `mise run setup` se encarga
  de todo.
- **Una cuenta del campus de Cesur** con acceso por Office 365.
- **Un proyecto de Google Cloud** con las APIs de Tasks y Calendar activadas y
  credenciales de aplicación de escritorio (`credentials.json`).
- **Un equipo donde dejarlo corriendo** si quieres sincronización automática: un
  contenedor, una VM o un Raspberry Pi con systemd valen de sobra.

## Puesta en marcha

### 1. Instalar

```bash
mise run setup          # uv sync + playwright install chromium
cp .env.example .env    # ajusta las rutas y nombres si quieres
```

### 2. Credenciales de Google

> [!NOTE]
> Los pasos para crear el proyecto en Google Cloud, activar las APIs y descargar
> `credentials.json` van aquí. _(Pendiente de redactar.)_

Deja el archivo descargado en la raíz del proyecto como `credentials.json` y
autoriza el acceso:

```bash
mise run google-login
```

Se abrirá el navegador para dar permiso y se guardará `token.json`. Los permisos
que se piden son los mínimos: gestión de Google Tasks y **solo** los calendarios
creados por esta app, nunca tu calendario principal.

### 3. Iniciar sesión en el campus

```bash
mise run login
```

Se abre una ventana de Chromium. Pulsa **Office 365**, completa el login y el 2FA,
acepta _mantener la sesión iniciada_ y espera al dashboard de «Mis Cursos». Vuelve
a la terminal, pulsa Enter y la sesión queda guardada en `browser_profile/`.

### 4. Sincronizar

```bash
mise run sync           # scrape + sincronización con Google
```

O por separado, `mise run scrape` para volcar el campus a `assignments.json` y
`mise run sync-google` para subirlo a Google.

## Configuración

Todo se ajusta desde el `.env` (ver [`.env.example`](.env.example)):

| Variable                    | Por defecto                                   | Qué controla                                                                            |
| --------------------------- | --------------------------------------------- | --------------------------------------------------------------------------------------- |
| `CESUR_BASE_URL`            | `https://campusonline2026.cesurformacion.com` | URL del campus.                                                                         |
| `CESUR_TIMEZONE`            | `Europe/Madrid`                               | Zona horaria de fechas y eventos.                                                       |
| `PROFILE_DIR`               | `./browser_profile`                           | Perfil de Chromium con la sesión del campus.                                            |
| `OUTPUT_FILE`               | `./assignments.json`                          | Volcado del scrape.                                                                     |
| `GOOGLE_CREDENTIALS_FILE`   | `./credentials.json`                          | Credenciales OAuth de Google Cloud.                                                     |
| `GOOGLE_TOKEN_FILE`         | `./token.json`                                | Token de acceso generado al autorizar.                                                  |
| `SYNC_STATE_FILE`           | `./sync_state.json`                           | Estado del sync (el ID del calendario creado).                                          |
| `GOOGLE_TASKLIST_NAME`      | _(vacío)_                                     | Lista de Google Tasks a usar; vacío = la lista por defecto.                             |
| `GOOGLE_CALENDAR_NAME`      | `Cesur`                                       | Nombre del calendario que se crea para las tutorías.                                    |
| `TUTORIAL_REMINDER_MINUTES` | `60`                                          | Minutos de aviso antes de cada tutoría. `none` = sin aviso; vacío = los del calendario. |
| `FORMAT_RULES_FILE`         | `./format_rules.toml`                         | Reglas de formato de los títulos.                                                       |
| `NTFY_TOPIC`                | _(vacío)_                                     | Topic de ntfy.sh para las alertas. Vacío = solo se imprimen por consola.                |

## Reglas de formato

Los títulos que llegan del campus son largos y repetitivos
(`Prueba Abierta 1 UD01 (Acceso a Datos - BAL)`). Con un `format_rules.toml` puedes
reescribirlos antes de enviarlos a Google, con reemplazos literales o regex:

```toml
[[rules]]
pattern = '^(.+?) \((.+?)(?: - [A-Z]{3})?\)$'
replace = '[\2] \1'
applies_to = ["tasks"]
```

Copia [`format_rules.example.toml`](format_rules.example.toml) para empezar y
prueba el resultado sin tocar nada en Google:

```bash
uv run cesur-sync-google --preview
```

## Ejecución automática

En [`systemd/`](systemd) hay un _service_ y un _timer_ que ejecutan el scrape y la
sincronización cada hora. Copia el proyecto a `/opt/cesur-sync` (con el
`browser_profile/` y el `token.json` ya generados en tu equipo) y activa el timer:

```bash
sudo cp systemd/moodle-sync.{service,timer} /etc/systemd/system/
sudo systemctl enable --now moodle-sync.timer
```

> [!IMPORTANT]
> La sesión del campus y el token de Google se generan **en un equipo con
> navegador** y se copian al servidor. Si caducan, vuelve a ejecutar `mise run login`
> o `mise run google-login` en local y copia de nuevo `browser_profile/` o
> `token.json`.

## Comandos

| Comando              | Tarea de mise           | Qué hace                                         |
| -------------------- | ----------------------- | ------------------------------------------------ |
| `cesur-login`        | `mise run login`        | Abre el navegador y guarda la sesión del campus. |
| `cesur-google-login` | `mise run google-login` | Autoriza Google Tasks y Calendar.                |
| `cesur-scrape`       | `mise run scrape`       | Extrae tareas y tutorías a `assignments.json`.   |
| `cesur-sync-google`  | `mise run sync-google`  | Sube el volcado a Google.                        |
| —                    | `mise run sync`         | Scrape + sincronización, de una tacada.          |
| —                    | `mise run lint` / `fmt` | Lint y formato con ruff.                         |

> [!WARNING]
> `browser_profile/`, `credentials.json`, `token.json` y `.env` contienen tu sesión
> y tus credenciales. Están en el `.gitignore` por algo: no los subas a ningún
> sitio.
