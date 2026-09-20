<div align="center">

# CesurSync

**Tus entregas y tutorías del campus, en tu móvil.**

Scraper del campus online de Cesur que vuelca las tareas con fecha de entrega en
Google Tasks y las tutorías programadas en Google Calendar. Se ejecuta solo, cada
hora, y te avisa si algo se rompe.

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776ab?style=flat-square&logo=python&logoColor=white)](https://www.python.org)
[![uv](https://img.shields.io/badge/gestionado%20con-uv-de5fe9?style=flat-square&logo=uv&logoColor=white)](https://docs.astral.sh/uv/)
[![Playwright](https://img.shields.io/badge/Playwright-Chromium-2ead33?style=flat-square&logo=playwright&logoColor=white)](https://playwright.dev/python/)
[![Google APIs](https://img.shields.io/badge/Google-Tasks%20%26%20Calendar-4285f4?style=flat-square&logo=google&logoColor=white)](https://developers.google.com/tasks)

[**🚀 Instalación y uso**](INSTALACION.md)

</div>

---

## Qué hace

El campus de Cesur es un Moodle detrás del SSO de Office 365: no hay API, y la UX
del calendario no es la la mejor.
Desde 2026, parece que el calendario no enseña todas las tareas programadas.

CesurSync automatiza la navegación y el scraping de tus asignaturas para que no tengas
que entrar en el campus cada vez que quieras ver qué tienes que entregar o qué tutorías
tienes programadas. Lo hace así:

- **Entra por ti.** Inicias sesión una vez con tu cuenta de Microsoft en un
  navegador real y la sesión queda guardada en un perfil de Chromium. A partir de
  ahí el scraper renueva el SSO en silencio.
- **Recorre tus asignaturas.** Lee el listado de cursos y, de cada uno, todas las
  tareas con fecha de entrega. Las tutorías las pide directamente al fragmento
  AJAX de Moodle, sin abrir la interfaz.
- **Sincroniza con Google.** Cada tarea se convierte en una tarea de Google Tasks
  con su fecha y su enlace; cada tutoría programada, en un evento de un calendario
  propio con recordatorio.
- **No pisa tu trabajo.** Las tareas que completas o borras no vuelven a aparecer,
  y las tutorías que se cancelan se eliminan del calendario.
- **Te avisa cuando hace falta.** Si caduca la sesión del campus o el token de
  Google, recibes una notificación por [ntfy](https://ntfy.sh) en vez de un
  silencio sospechoso.

Los títulos se pueden reescribir a tu gusto antes de enviarlos a Google, con
reglas de formato en un TOML, por ejemplo:
de `Prueba Abierta 1 UD01 (Acceso a Datos - BAL)` a `[Acceso a Datos] Prueba Abierta 1 UD01`.

## Empezar

Necesitas Python 3.12+, [uv](https://docs.astral.sh/uv/), una cuenta del campus y
un proyecto de Google Cloud con las APIs de Tasks y Calendar activadas. El camino
corto, una vez tienes tu `credentials.json`:

```bash
mise run setup          # uv sync + playwright install chromium
mise run google-login   # autoriza Google Tasks y Calendar
mise run login          # inicia sesión en el campus (abre el navegador)
mise run sync           # scrape + sincronización
```

La guía completa —credenciales de Google, variables del `.env`, reglas de formato
y ejecución horaria con systemd— está en
[**INSTALACION.md**](INSTALACION.md).

> [!WARNING]
> `browser_profile/`, `credentials.json`, `token.json` y `.env` contienen tu sesión
> y tus credenciales. Están en el `.gitignore` por algo: no los subas a ningún
> sitio.

## Disclaimer

> [!WARNING]
> **A los sysadmins de Cesur:**
>
> Este proyecto no hace nada que no se pueda hacer manualmente con un navegador.
> No intenta vulnerar la seguridad del campus ni el SSO de Microsoft. Solo automatiza
> la navegación y el scraping de datos que ya son visibles para el usuario.
>
> La UI-UX del Campus es muy mejorable, y este proyecto es un intento de hacerla más usable para
> estudiantes.
>
> Si no os gusta este proyecto, podéis añadir una API o feed de calendario para estudiantes, gracias!
