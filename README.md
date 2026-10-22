# Plant Report

Automatiza la revisión diaria de plantas: valida que la configuración de cada cámara no haya
cambiado y que no se haya movido (comparando su `.json` y su imagen contra una referencia base),
persiste el resultado en PostgreSQL, genera un reporte ejecutivo en PDF por cliente, y lo envía por
correo. Ver [ROADMAP.md](ROADMAP.md) para el contexto completo del proyecto (decisiones, diseño,
experimentos) — este README es solo la guía práctica de instalación y uso.

El ordenamiento de los `.log` de revisión no es parte de este proyecto: lo hace el programa externo
de revisión de cámaras antes de que estos archivos lleguen aquí.

## Instalación

```powershell
pipenv install
```

## Base de datos

Se necesita un PostgreSQL accesible (por defecto, uno corriendo en la misma máquina). Con las
credenciales ya puestas en `.env` (ver abajo), aplica el esquema una sola vez:

```powershell
pipenv run python migrate.py
```

Vuelve a correrlo sin problema si se agregan migraciones nuevas más adelante (`migrations/*.sql`) —
no repite las que ya aplicó.

## Configuración (`.env`)

Copia `.env.example` a `.env` y ajusta los valores a tu entorno (el archivo no se versiona):

```powershell
copy .env.example .env
```

| Variable | Significado |
| --- | --- |
| `CHECK_PLANTS_ROOT` | Carpeta raíz donde el programa externo de revisión deja los `.log`, imágenes y `.json` de configuración, con la estructura `[Cliente]\[Mes]\[ddmmyy]\[Planta]\[Servidor]\`. |
| `CONFIG_BASE_ROOT` | Configuración "base" de referencia de cada cámara (`[Cliente]\[Planta]\[Servidor]\[Cámara].json`). Se crea sola la primera vez que se procesa una cámara sin base. |
| `IMAGE_BASE_ROOT` | Imagen "base" de referencia de cada cámara (`[Cliente]\[Planta]\[Servidor]\[Cámara].jpg`). También se crea sola la primera vez. |
| `REPORTES_ROOT` | Carpeta donde se guardan los PDFs del reporte ejecutivo, uno por cliente: `REPORTES_ROOT\[Cliente]\[DDMMYYYY]_[Cliente].pdf`. |
| `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` | Conexión a PostgreSQL. |
| `MONIT_API_URL` | URL base de la API de `Monit_Servers_V2` (proyecto hermano), para traer temperatura CPU/GPU y uso de disco de cada servidor. Si un servidor no existe ahí, el reporte muestra "Sin datos" sin bloquear nada. |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_APP_PASSWORD` | Cuenta de correo (Google Workspace) usada para enviar el reporte. `SMTP_APP_PASSWORD` es una contraseña de aplicación (myaccount.google.com → Seguridad → Verificación en 2 pasos → Contraseñas de aplicaciones), no la contraseña normal de la cuenta. |
| `REPORTE_ASUNTO` | Plantilla del asunto del correo, con `[Cliente]` como placeholder. |
| `REPORTE_CUERPO` | Plantilla del cuerpo del correo (texto plano, se arma como HTML con la firma de Quantum Labs debajo), con `[cliente]` como placeholder. |
| `REPORTE_DESTINATARIOS_DEFAULT` | Destinatarios (separados por coma) que se usan si un cliente no tiene su propia variable. |
| `REPORTE_DESTINATARIOS_<CLIENTE>` | Destinatarios específicos de un cliente (nombre normalizado a mayúsculas, ej. `REPORTE_DESTINATARIOS_API_MANZANILLO`). Opcional — sin esto, ese cliente usa el default. |

## Uso diario

```powershell
pipenv run python main.py
```

Pide la fecha a procesar (`ddmmyy`, o `h` para hoy) y, para cada cámara encontrada ese día (o que
falló por completo según el `.log` del servidor):

1. Compara su `.json` contra `CONFIG_BASE_ROOT` (detecta la marca automáticamente — AXIS, HIKVISION,
   VIVOTEK, DAHUA).
2. Compara su `.jpg` contra `IMAGE_BASE_ROOT` (dos señales: features/homografía + correlación de
   fase).
3. Si la imagen da `REVISAR`, abre una ventana para que un humano confirme si la cámara se movió de
   verdad, si es un falso positivo, o si hay que marcar la base como desactualizada (ver
   `ventana_bases.py` abajo) — a menos que ya esté confirmada como movida de un día anterior, en
   cuyo caso no se vuelve a preguntar.
4. Guarda el resultado en PostgreSQL (cámara por cámara, justo después de resolverla).

Al terminar, pregunta si generar el reporte ejecutivo y si enviarlo por correo.

### Banderas

| Bandera | Para qué sirve |
| --- | --- |
| `--sin-interaccion` | No abre la ventana de revisión (los `REVISAR` quedan sin resolver, pendientes para otro día); genera y envía el reporte automáticamente, sin preguntar. |
| `--cliente NOMBRE` | Procesa, reporta y envía correo solo de ese cliente (nombre exacto de su carpeta bajo `CHECK_PLANTS_ROOT`). Sin esto, corre todos los clientes encontrados esa fecha. |
| `--fecha FECHA` | Fecha a procesar (`ddmmyy` o `h`), sin preguntar en la terminal. Necesaria junto con `--sin-interaccion` para una corrida verdaderamente desatendida (ej. tarea programada) — sin ella, igual se queda esperando la fecha. |

Ejemplo para una corrida automática sin nadie presente:

```powershell
pipenv run python main.py --sin-interaccion --fecha h
```

## Ventanas

- **`ventana_revision.py`** — se abre sola desde `main.py` cuando hace falta revisar una cámara; no
  se corre por separado.
- **`ventana_bases.py`** — ventana aparte, independiente de la corrida diaria, para reemplazar las
  bases de imagen marcadas como desactualizadas con una foto limpia elegida a mano:

  ```powershell
  pipenv run python ventana_bases.py
  ```

## Scripts de administración (uso puntual, no parte de la corrida diaria)

| Script | Para qué sirve |
| --- | --- |
| `migrate.py` | Aplica el esquema de base de datos (ver "Base de datos" arriba). |
| `bootstrap_config_base.py` | Llena de una sola vez las bases de configuración que falten, usando el `.json` más reciente disponible por cámara. No sobrescribe bases existentes. |
| `bootstrap_image_base.py` | Igual que el anterior, pero para las bases de imagen. |
| `backfill_reportes.py` | Vuelve a correr la comparación sobre un rango de fechas pasadas **sin tocar la base de datos** (ni enviar correos) — solo para revisar resultados sobre datos históricos. |
| `diagnostico_jpeg.py` | Revisa si alguna imagen real falla al decodificarse (más allá de los avisos de "Corrupt JPEG" que a veces se ven en consola, que normalmente son inofensivos). |
| `scripts/mock_reporte_ejecutivo.py` | Genera un PDF de muestra del reporte ejecutivo con datos inventados, para revisar el diseño sin tocar ninguna base de datos real. |

## Script de captura independiente

`script/capture_img/` es una carpeta aparte, pensada para copiarse a cada servidor y capturar una
imagen directo de una cámara (útil para tener una foto limpia antes de reemplazar una base
desactualizada). Ver su propio [README](script/capture_img/README.md).
