# Plant Report

Automatiza la revisión de plantas: valida que la configuración de cada cámara
no haya cambiado y que no se haya movido (comparando su `.json` y su imagen
contra una referencia base), guarda los resultados en base de datos y genera
un reporte ejecutivo. Ver [ROADMAP.md](ROADMAP.md) para el contexto completo
del proyecto.

El ordenamiento de los `.log` de revisión ya no es parte de este proyecto: lo
hace el programa de revisión de cámaras antes de que estos archivos lleguen aquí.

## Instalación

```powershell
pipenv install
```

## Configuración (`.env`)

El proyecto lee la ubicación de los datos desde un archivo `.env` en la raíz (no se
versiona). Copia `.env.example` y ajusta las rutas a tu entorno:

```powershell
copy .env.example .env
```

| Variable | Significado |
| --- | --- |
| `CHECK_PLANTS_ROOT` | Carpeta raíz donde viven los `.log`, imágenes y `.json` de configuración de revisión (ej. `D:\Imágenes\Quantum Labs\Check Plants`). Dentro de ella se espera la estructura `[Cliente]\[Mes]\[ddmmyy]\[Planta]\[Servidor]\`. |
| `CONFIG_BASE_ROOT` | Carpeta donde vive la configuración "base" de referencia de cada cámara (ej. `D:\Imágenes\Quantum Labs\Config Base`), estructurada `[Cliente]\[Planta]\[Servidor]\[CAMARA].json` (sin fecha, es una referencia viva). Se crea sola la primera vez que se procesa una cámara sin base; de ahí en adelante queda fija hasta que se actualice a propósito. |

## Uso

```powershell
python main.py
```

Pide la fecha a procesar (`ddmmyy`) y, para cada cámara con `.json` de ese día
bajo `CHECK_PLANTS_ROOT`, detecta su marca (AXIS, HIKVISION o VIVOTEK — DAHUA
pendiente) y compara un subconjunto curado de campos (Imagen, Video,
Compresión, Network) contra su base en `CONFIG_BASE_ROOT`. Ver
[ROADMAP.md](ROADMAP.md), Fase 1, para el detalle de campos por marca y las
decisiones de diseño.
