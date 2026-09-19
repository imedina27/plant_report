# Plant Report

Automatiza la revisión de plantas: valida que las cámaras no se hayan movido
(comparando contra una imagen base), guarda los resultados en base de datos y
genera un reporte ejecutivo. Ver [ROADMAP.md](ROADMAP.md) para el contexto
completo del proyecto.

El ordenamiento de los `.log` de revisión ya no es parte de este proyecto: lo
hace el programa de revisión de cámaras antes de que estos archivos lleguen aquí.

## Instalación

```powershell
pipenv install
```

## Configuración (`.env`)

El proyecto lee la ubicación de los datos desde un archivo `.env` en la raíz (no se
versiona). Copia `.env.example` y ajusta la ruta a tu entorno:

```powershell
copy .env.example .env
```

| Variable            | Significado                                                                                                                                                                                       |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `CHECK_PLANTS_ROOT` | Carpeta raíz donde viven los `.log` e imágenes de revisión (ej. `D:\Imágenes\Quantum Labs\Check Plants`). Dentro de ella se espera la estructura `[Cliente]\[Mes]\[ddmmyy]\[Planta]\[Servidor]\`. |
