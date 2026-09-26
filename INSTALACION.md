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

CesurSync habla con Google Tasks y Google Calendar como una aplicación de
escritorio tuya: no hay servidor intermedio ni cuenta compartida. Eso significa
crear un proyecto en Google Cloud y descargar tus propias credenciales OAuth.
Son unos diez minutos y se hace una sola vez.


#### 2.1. Crear el proyecto

Entra en [console.cloud.google.com](https://console.cloud.google.com) y abre el
selector de proyecto de la barra superior.

<img src="https://github.com/user-attachments/assets/628a5163-0dce-439f-819c-f0ed7c5a3478" alt="Selector de proyecto en la barra superior de Google Cloud" width="400">

Pulsa **New project** arriba a la derecha del diálogo.

<img src="https://github.com/user-attachments/assets/58f03939-8793-4b26-b8d3-800557becca6" alt="Botón New project en el selector" width="177">

Ponle el nombre que quieras —aquí `Cesur Sync`—, deja **No organization** como
recurso padre y pulsa **Create**. El _Project ID_ se genera solo y da igual cuál
sea.

<img src="https://github.com/user-attachments/assets/b2d43f37-403b-437d-a93e-9a65fec47a01" alt="Formulario de nuevo proyecto con el nombre Cesur Sync" width="444">

Cuando termine de crearse, asegúrate de tenerlo **seleccionado** en la barra
superior: todo lo que viene después se configura dentro de este proyecto.

#### 2.2. Activar las APIs de Tasks y Calendar

Un proyecto nuevo no tiene ninguna API activa. Abre el menú ☰ y ve a
**APIs & Services**.

<img src="https://github.com/user-attachments/assets/e3571aa3-bb87-4746-a336-1a8273297355" alt="Menú de Google Cloud con APIs & Services desplegado" width="396">

Pulsa **+ Enable APIs and services**.

<img src="https://github.com/user-attachments/assets/6016d5b0-6ee0-4d2e-aaf3-297cd1960248" alt="Botón Enable APIs and services" width="410">

Busca `Google Tasks API`, ábrela y pulsa **Enable**.

<img src="https://github.com/user-attachments/assets/a29c79fa-1700-4a4c-bd2f-e2ff678fd446" alt="Ficha de Google Tasks API con el botón Enable" width="500">

Vuelve atrás y repite con `Google Calendar API`.

<img src="https://github.com/user-attachments/assets/58d9abd6-3f04-4b80-a8ab-7f195bd655f4" alt="Ficha de Google Calendar API con el botón Enable" width="562">

> [!NOTE]
> Son las dos únicas APIs que necesita el proyecto. Si te dejas una, el sync
> fallará con un error `accessNotConfigured` la primera vez que la use.

#### 2.3. Configurar la pantalla de consentimiento

Ahora toca decirle a Google qué app es esta y quién la usa. Menú ☰ →
**APIs & Services** → **Credentials**.

<img src="https://github.com/user-attachments/assets/9786efc7-18cc-45a5-b6bc-afc7a6b01214" alt="Menú de Google Cloud con Credentials resaltado" width="372">

Pulsa **+ Create credentials** y elige **OAuth client ID**.

<img src="https://github.com/user-attachments/assets/72f24389-4776-4995-bf3a-c2b450606234" alt="Menú Create credentials con la opción OAuth client ID" width="620">

Google no te dejará seguir hasta configurar la pantalla de consentimiento.
Pulsa **Configure consent screen**.

<img src="https://github.com/user-attachments/assets/3fc74349-6dc9-4ae0-ba13-7368b4ab441c" alt="Aviso de que hay que configurar la pantalla de consentimiento" width="620">

En **App Information**, pon el nombre de la app (`Cesur Sync`) y tu correo de
soporte —el tuyo, eres el único usuario—. **Next**.

<img src="https://github.com/user-attachments/assets/fcece09a-dd65-4e02-8411-c5e7a62885ce" alt="Formulario App Information con el nombre y el correo de soporte" width="573">

En **Audience**, elige **External**. _Internal_ solo está disponible si tu cuenta
pertenece a una organización de Google Workspace; con una cuenta de Gmail normal,
External es la única opción.

<img src="https://github.com/user-attachments/assets/63b3ab2a-b931-435c-b6df-75d084c5fcfa" alt="Selección de audiencia External" width="595">

En **Contact Information**, tu correo otra vez. Es donde Google avisa de cambios
en el proyecto.

<img src="https://github.com/user-attachments/assets/f95bdab6-1070-4f13-88ce-e6b50aa66f4e" alt="Formulario de datos de contacto" width="565">

Acepta la _User Data Policy_ y pulsa **Continue**.

<img src="https://github.com/user-attachments/assets/bc19af66-0126-40a4-9afd-b903d73a45b6" alt="Casilla de aceptación de la política de datos y botón Continue" width="456">

#### 2.4. Crear el cliente OAuth y descargar `credentials.json`

Con el consentimiento configurado, ya puedes crear el cliente. Desde
**OAuth Overview**, pulsa **Create OAuth client**.

<img src="https://github.com/user-attachments/assets/b3782674-b423-443b-8ff5-dfb339f60e42" alt="Pantalla OAuth Overview con el botón Create OAuth client" width="620">

Elige **Application type: Desktop app**, ponle nombre y pulsa **Create**.

> [!IMPORTANT]
> Tiene que ser **Desktop app**. CesurSync usa el flujo `InstalledAppFlow`, que
> levanta un servidor local temporal para recibir el código de autorización; con
> un cliente de tipo _Web application_ el login falla con `redirect_uri_mismatch`.

<img src="https://github.com/user-attachments/assets/5519b78c-f388-49ad-95fb-e64b16061ed8" alt="Formulario de cliente OAuth con Desktop app seleccionado" width="587">

Al crearse, descarga el JSON y guárdalo en la raíz del proyecto como
`credentials.json` (o donde apunte `GOOGLE_CREDENTIALS_FILE` en tu `.env`).

<img src="https://github.com/user-attachments/assets/52b8d54b-e50d-467c-8004-d72703133231" alt="Botón Download JSON del cliente recién creado" width="196">

#### 2.5. Publicar la app

Este paso es opcional en apariencia y obligatorio en la práctica: mientras la app
esté en modo **Testing**, el _refresh token_ que guarda `token.json` **caduca a los
7 días** y tendrías que reautorizar cada semana. Publicándola en producción deja
de caducar.

Busca `audience` en la barra de búsqueda de la consola y abre la página
**Audience** de Google Auth Platform.

<img src="https://github.com/user-attachments/assets/c58ab912-67f6-4606-baaf-22aa12999d2a" alt="Búsqueda de la página Audience en la consola" width="326">

Verás el estado **Testing** y el botón **Publish app** deshabilitado hasta
completar la página de _Branding_.

<img src="https://github.com/user-attachments/assets/121af598-3977-4e83-b810-7a7bde471639" alt="Estado de publicación en Testing con Publish app deshabilitado" width="505">

Ve a **Branding** y rellena los tres enlaces —página principal, política de
privacidad y términos de servicio—. Para uso personal vale con apuntar los tres
al repositorio del proyecto.

<img src="https://github.com/user-attachments/assets/f2511acb-b1df-4323-adf3-fc6ee965cbbb" alt="Página de Branding con los enlaces del dominio de la app" width="555">

Vuelve a **Audience**. Ahora **Publish app** está disponible.

<img src="https://github.com/user-attachments/assets/7f9d8971-c9c8-48b1-86f3-02c29df236c9" alt="Estado de publicación con el botón Publish app activo" width="283">

Confirma el paso a producción.

<img src="https://github.com/user-attachments/assets/f6e08275-7fde-45ab-8fc8-cd90646c87d4" alt="Diálogo de confirmación Push to production" width="602">

> [!NOTE]
> Publicar **no** significa pasar la verificación de Google. La app sigue sin
> verificar y seguirá mostrando el aviso del paso siguiente, pero el token ya no
> caduca. Para uso personal no hace falta verificarla: el límite de una app sin
> verificar en producción es de 100 usuarios y aquí eres uno.

#### 2.6. Autorizar el acceso

Con `credentials.json` en su sitio, ejecuta:

```bash
mise run google-login
```

Se abrirá el navegador. Elige la cuenta de Google donde quieres las tareas y el
calendario.

<img src="https://github.com/user-attachments/assets/5fb98488-a17b-46e7-bc65-5636a324be3a" alt="Selector de cuenta de Google para continuar a Cesur Sync" width="620">

Como la app no está verificada, Google enseña un aviso rojo. Es tu propia app:
pulsa **Advanced**.

<img src="https://github.com/user-attachments/assets/a8e45cf6-909b-4220-ac95-b49381f1e57f" alt="Aviso de Google: esta app no está verificada" width="620">

Y luego **Go to Cesur Sync (unsafe)**.

<img src="https://github.com/user-attachments/assets/17f35c75-aba3-4dc4-9bd8-ebcab422489c" alt="Enlace Go to Cesur Sync (unsafe) tras desplegar Advanced" width="620">

Por último, **marca las dos casillas** (o **Select all**) y continúa.

<img src="https://github.com/user-attachments/assets/bdd57d61-526b-42ba-a64b-e18a3eb6411c" alt="Pantalla de permisos con los dos scopes marcados" width="607">

> [!IMPORTANT]
> Si dejas alguna casilla sin marcar, la autorización se guarda incompleta y el
> sync fallará con un error de permisos. En ese caso, borra `token.json` y vuelve
> a ejecutar `mise run google-login`.

Al terminar se guarda `token.json` y ya no hace falta volver a pasar por aquí.
Los permisos que se piden son los mínimos:

| Scope                                   | Qué permite                                                             |
| --------------------------------------- | ----------------------------------------------------------------------- |
| `https://www.googleapis.com/auth/tasks` | Crear y actualizar tus tareas en Google Tasks.                          |
| `.../auth/calendar.app.created`         | Gestionar **solo** los calendarios creados por esta app, nunca el tuyo. |

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
sincronización cada hora. Las rutas del _service_ apuntan a `/opt/cesur-sync`: si
instalas el proyecto en otro sitio, cámbialas antes de copiarlo a systemd.

### 1. Preparar el servidor

Copia el proyecto a `/opt/cesur-sync`, instálalo con `mise run setup` y añade las
librerías del sistema que necesita Chromium, que en una instalación mínima de
Debian o Ubuntu no vienen:

```bash
uv run playwright install-deps chromium
```

Copia también desde tu equipo `.env`, `credentials.json`, `token.json` y, si ya
has sincronizado desde él, `sync_state.json` (sin él, el servidor crea un
calendario nuevo en lugar de reutilizar el tuyo). El token de Google es un JSON
normal y funciona en cualquier sistema.

### 2. Iniciar sesión en el campus desde el servidor

> [!IMPORTANT]
> `browser_profile/` **no se puede copiar desde macOS ni desde Windows**. Chromium
> cifra las cookies con una clave propia de cada sistema (el llavero en macOS,
> DPAPI en Windows), así que el perfil llega al servidor sin sesión y el scrape
> avisa de que ha caducado. Solo funciona copiarlo de un Linux a otro.

Lo más sencillo es hacer el login en el propio servidor, con la ventana de
Chromium reenviada a tu equipo por SSH (X11):

- **macOS**: instala [XQuartz](https://www.xquartz.org) y **cierra sesión y vuelve a
  entrar** antes de usarlo. Si no, rechaza las conexiones.
- **Windows**: en vez de X11, ejecuta `mise run login` dentro de WSL y copia ese
  `browser_profile/` al servidor. Es un perfil de Linux, así que sí funciona.
- **Servidor**: necesita `X11Forwarding yes` en `/etc/ssh/sshd_config` y el paquete
  `xauth`. En contenedores LXC sin IPv6, añade también `AddressFamily inet` o el
  reenvío falla sin avisar.

```bash
ssh -Y usuario@servidor
echo $DISPLAY                 # debe mostrar algo como localhost:10.0
cd /opt/cesur-sync && mise run login
```

### 3. Activar el timer

```bash
sudo cp systemd/moodle-sync.{service,timer} /etc/systemd/system/
sudo systemctl enable --now moodle-sync.timer
sudo systemctl start moodle-sync.service      # primera ejecución, para comprobarlo
journalctl -u moodle-sync.service -n 50
```

Si la sesión del campus caduca, repite el paso 2. Si caduca el token de Google,
vuelve a ejecutar `mise run google-login` en tu equipo y copia de nuevo
`token.json`.

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
