# Plant Report

Automatiza la revisión diaria de plantas: valida que la configuración de cada cámara no haya
cambiado y que no se haya movido (comparando su `.json` y su imagen contra una referencia base),
persiste el resultado en PostgreSQL, genera un reporte ejecutivo en PDF por cliente, y lo envía por
correo. Ver [ROADMAP.md](ROADMAP.md) para el contexto completo del proyecto (decisiones, diseño,
experimentos) — este README es solo la guía práctica de instalación y uso.

El ordenamiento de los `.log` de revisión no es parte de este proyecto: lo hace el programa externo
de revisión de cámaras antes de que estos archivos lleguen aquí.

## Estructura del proyecto

Los puntos de entrada (lo que se corre directo) están en la raíz; todo lo demás está agrupado por
responsabilidad en paquetes, pensados para poder reutilizarse en otros programas más adelante:

| Carpeta | Contiene |
| --- | --- |
| *(raíz)* | Puntos de entrada: `main.py`, `generar_reporte.py`, `migrate.py`. |
| `comparacion/` | Lógica pura de comparación -- `config_compare.py`, `image_compare.py`, `log_parse.py`. Sin base de datos, red ni UI. |
| `persistencia/` | `db.py` -- todo el acceso a PostgreSQL. |
| `reporte/` | `datos_reporte.py` (arma los datos) y `reporte_ejecutivo.py` (arma el PDF). |
| `integraciones/` | Clientes de sistemas externos -- `monit_client.py` (Monit_Servers_V2) y `correo.py` (SMTP). |
| `ui/` | Ventanas Tkinter -- `ventana_revision.py` y `ventana_bases.py`. |
| `scripts/` | Scripts de administración de un solo uso (ver tabla abajo). |
| `migrations/` | Archivos `.sql` del esquema de base de datos. |
| `diagramas/` | Diagramas de flujo del proyecto (Mermaid). |
| `assets/` | Logo y recursos visuales compartidos. |

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
| `IMAGE_BASE_ROOT` | Imagen "base" de referencia de cada cámara (`[Cliente]\[Planta]\[Servidor]\[Cámara].jpg`) -- siempre una foto real de un solo día, la que se le muestra a un humano (ventana de revisión, ventana de bases, PDF del reporte). También se crea sola la primera vez. |
| `IMAGE_BASE_MEDIANA_ROOT` | Mediana por píxel de los últimos días de la cámara (mismo formato de ruta que `IMAGE_BASE_ROOT`), usada **solo** por el algoritmo de comparación -- nunca se le muestra a un humano, para no confundir con "fantasmas" de vehículos/personas que mezclar varios días puede dejar. Se llena sola cuando hay suficiente historial (ver ROADMAP.md, 26-27/10/2026). |
| `IMAGE_HISTORY_ROOT` | Copia fechada del `.jpg` de cada cámara, últimos 10 días (`[Cliente]\[Planta]\[Servidor]\[Cámara]\[AAAA-MM-DD].jpg`). Se llena sola; es de donde sale la mediana de `IMAGE_BASE_MEDIANA_ROOT` (ver ROADMAP.md). |
| `REPORTES_ROOT` | Carpeta donde se guardan los PDFs del reporte ejecutivo, uno por cliente: `REPORTES_ROOT\[Cliente]\[DDMMYYYY]_[Cliente].pdf`. |
| `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` | Conexión a PostgreSQL. |
| `MONIT_API_URL` | URL base de la API de `Monit_Servers_V2` (proyecto hermano), para traer temperatura CPU/GPU y uso de disco de cada servidor. Si un servidor no existe ahí, o si la API no responde (caída, sin VPN, etc.), el reporte muestra "Sin datos" sin bloquear nada. |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_APP_PASSWORD` | Cuenta de correo (Google Workspace) usada para enviar el reporte. `SMTP_APP_PASSWORD` es una contraseña de aplicación (myaccount.google.com → Seguridad → Verificación en 2 pasos → Contraseñas de aplicaciones), no la contraseña normal de la cuenta. |
| `REPORTE_ASUNTO` | Plantilla del asunto del correo, con `[Cliente]` como placeholder. |
| `REPORTE_CUERPO` | Plantilla del cuerpo del correo (texto plano, se arma como HTML con la firma de Quantum Labs debajo), con `[cliente]` como placeholder. |
| `REPORTE_DESTINATARIOS_DEFAULT` | Destinatarios (separados por coma) que se usan si un cliente no tiene su propia variable. |
| `REPORTE_DESTINATARIOS_<CLIENTE>` | Destinatarios específicos de un cliente (nombre normalizado a mayúsculas, ej. `REPORTE_DESTINATARIOS_API_MANZANILLO`). Opcional — sin esto (o si se deja vacío), ese cliente usa el default. Para que a un cliente específico no se le envíe nada, usa el valor `NINGUNO` (no sirve dejarlo vacío, eso cae al default igual). |

## Uso diario

```powershell
pipenv run python main.py
```

Pide la fecha a procesar (`ddmmyy`, o `h` para hoy). Antes de procesar cámaras, por cada servidor
revisa si su(s) servicio(s) de IA (uno o más puertos, según el `.log`) pudieron leer su YAML de
configuración ese día -- si no, es un problema de infraestructura (Quantum Labs), no de la
cámara/red del cliente, y queda guardado por separado (avisa en consola solo si cambió de estado).
Después, para cada cámara encontrada ese día (o que falló por completo según el `.log` del
servidor):

1. Compara su `.json` contra `CONFIG_BASE_ROOT` (detecta la marca automáticamente — AXIS, HIKVISION,
   VIVOTEK, DAHUA).
2. Compara su `.jpg` contra `IMAGE_BASE_ROOT` (dos señales: features/homografía + correlación de
   fase).
3. Si la imagen da `REVISAR` -- o si da `NO CONCLUYENTE` tres días seguidos -- abre una ventana para
   que un humano confirme si la cámara se movió de verdad, si es un falso positivo, o si hay que
   marcar la base como desactualizada (ver `ui/ventana_bases.py` abajo) — a menos que ya esté
   confirmada como movida de un día anterior, en cuyo caso no se vuelve a preguntar.
4. Guarda el resultado en PostgreSQL (cámara por cámara, justo después de resolverla).

Al terminar, pregunta si generar el reporte ejecutivo y si enviarlo por correo.

### Banderas

| Bandera | Para qué sirve |
| --- | --- |
| `--no-interaction` | No abre la ventana de revisión (los `REVISAR` quedan sin resolver, pendientes para otro día); genera y envía el reporte automáticamente, sin preguntar. |
| `--client NOMBRE` | Procesa, reporta y envía correo solo de ese cliente (nombre exacto de su carpeta bajo `CHECK_PLANTS_ROOT`). Sin esto, corre todos los clientes encontrados esa fecha. |
| `--date FECHA` | Fecha a procesar (`ddmmyy` o `h`), sin preguntar en la terminal. Necesaria junto con `--no-interaction` para una corrida verdaderamente desatendida (ej. tarea programada) — sin ella, igual se queda esperando la fecha. |

Ejemplo para una corrida automática sin nadie presente:

```powershell
pipenv run python main.py --no-interaction --date h
```

## Ventanas

- **`ui/ventana_revision.py`** — se abre sola desde `main.py` cuando hace falta revisar una
  cámara; no se corre por separado (su demo manual sí se puede correr con
  `pipenv run python -m ui.ventana_revision`, ver el `if __name__ == "__main__"` del archivo).
- **`ui/ventana_bases.py`** — ventana aparte, independiente de la corrida diaria, para reemplazar
  las bases de imagen marcadas como desactualizadas con una foto limpia elegida a mano:

  ```powershell
  pipenv run python -m ui.ventana_bases
  ```

## Scripts de administración (uso puntual, no parte de la corrida diaria)

| Script | Para qué sirve |
| --- | --- |
| `migrate.py` | Aplica el esquema de base de datos (ver "Base de datos" arriba). |
| `generar_reporte.py` | Genera (y pregunta si enviar) el reporte ejecutivo de una fecha que ya se procesó con `main.py`, sin repetir la comparación de cámaras ni la revisión humana -- usa lo que ya quedó guardado en la base de datos. Útil si esa corrida se hizo sin generar el reporte por error. Mismas banderas que `main.py`: `--no-interaction`, `--client`, `--date`. |
| `scripts/bootstrap_config_base.py` | Llena de una sola vez las bases de configuración que falten, usando el `.json` más reciente disponible por cámara. No sobrescribe bases existentes. |
| `scripts/bootstrap_image_base.py` | Igual que el anterior, pero para las bases de imagen. |
| `scripts/backfill_reportes.py` | Vuelve a correr la comparación sobre un rango de fechas pasadas **sin tocar la base de datos** (ni enviar correos) — solo para revisar resultados sobre datos históricos. |
| `scripts/diagnostico_jpeg.py` | Revisa si alguna imagen real falla al decodificarse (más allá de los avisos de "Corrupt JPEG" que a veces se ven en consola, que normalmente son inofensivos). |
| `scripts/mock_reporte_ejecutivo.py` | Genera un PDF de muestra del reporte ejecutivo con datos inventados, para revisar el diseño sin tocar ninguna base de datos real. |
| `scripts/separar_base_mediana.py` | Migración de una sola vez (27/10/2026): separa `IMAGE_BASE_ROOT` (foto real) de `IMAGE_BASE_MEDIANA_ROOT` (mediana) para cámaras que ya se habían promovido antes de que existiera esa separación. Usa un detector de objetos (YOLO, dependencia `ultralytics`) para elegir una foto del mes sin vehículos/personas. Admite `--dry-run`, `--client`, `--camera`. |
| `scripts/revisar_bases.py` | Auditoría visual rápida: muestra, cámara por cámara, la base real de un servidor (`--client`/`--plant`/`--server`) y deja marcarla como `base_desactualizada` con un clic, o pasar a la siguiente sin hacer nada. Las ya marcadas se saltan solas. Sin banderas, lista las combinaciones cliente/planta/servidor disponibles. |

## Script de captura independiente

`script/capture_img/` es una carpeta aparte, pensada para copiarse a cada servidor y capturar una
imagen directo de una cámara (útil para tener una foto limpia antes de reemplazar una base
desactualizada). Ver su propio [README](script/capture_img/README.md).
