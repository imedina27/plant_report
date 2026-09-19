# Plant Report

Herramienta para ordenar los `.log` generados por la revisión diaria de cámaras de
planta (agrupa por cámara/servidor lo que el proceso original escribe entrelazado
por ejecutarse en paralelo). Ver [ROADMAP.md](ROADMAP.md) para el contexto completo
del proyecto.

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

| Variable            | Significado                                                                                   |
|---------------------|------------------------------------------------------------------------------------------------|
| `CHECK_PLANTS_ROOT`  | Carpeta raíz donde viven los `.log` e imágenes de revisión (ej. `D:\Imágenes\Quantum Labs\Check Plants`). Dentro de ella se espera la estructura `[Cliente]\[Mes]\[ddmmyy]\[Planta]\[Servidor]\`. |

## Uso

```powershell
python main.py
```

Pide la fecha de la corrida a ordenar (formato `ddmmyy`, ej. `180926`) y procesa
todos los `.log` de esa fecha bajo `CHECK_PLANTS_ROOT` (tanto los `.log` por
servidor/cámara como los `resumen_[fecha].log` por cliente). Antes de sobrescribir
cada archivo guarda una copia `.bak`.

## Reglas de ordenamiento por cliente (`sort_rules/`)

No todos los clientes deben ordenarse igual (ver más abajo). `log_sorter.py`
determina el cliente a partir del nombre de la primera carpeta bajo
`CHECK_PLANTS_ROOT` (ej. `AbInBev`, `Others`) y busca un archivo de reglas para
ese nombre exacto:

1. Si existe `sort_rules/<Cliente>.json`, sus claves sobrescriben las del default
   (no hace falta repetir las que no cambian).
2. Si no existe, se usa `sort_rules/default.json` tal cual.

Esto significa que un cliente/carpeta nuevo que aparezca no necesita ningún cambio
de código: simplemente hereda las reglas generales de `default.json` hasta que se
le cree su propio archivo.

### Cómo crear reglas para un cliente

Crea `sort_rules/<NombreExactoDeLaCarpeta>.json` (sensible a mayúsculas/minúsculas,
debe coincidir con el nombre de la carpeta dentro de `Check Plants`). Ejemplo real,
`sort_rules/AbInBev.json`:

```json
{
    "plant_order": "lowest_server_number",
    "servidor_order": "numeric_suffix",
    "camera_order": "alpha"
}
```

`sort_rules/default.json` (lo que usa cualquier cliente sin config propio):

```json
{
    "plant_order": "alpha",
    "servidor_order": "alpha",
    "camera_order": "alpha"
}
```

### Opciones disponibles

**`plant_order`** — cómo se ordenan entre sí los bloques de planta en la sección
`DETALLE POR PLANTA - CÁMARAS CON FALLAS` del `resumen_[fecha].log`:

| Valor | Significado |
|---|---|
| `"alpha"` (default) | Los bloques de planta van en orden alfabético por nombre de planta. |
| `"lowest_server_number"` | Los bloques de planta van ordenados según el número más bajo de servidor que contengan (caso especial de AbInBev: una planta con los servidores 01 y 02 va antes que una con el servidor 03, sin importar el nombre de la planta). |

**`servidor_order`** — cómo se ordenan los servidores entre sí dentro de una misma
planta (aplica tanto al `resumen` como, indirectamente, a qué tan agrupados quedan
sus `.log`):

| Valor | Significado |
|---|---|
| `"alpha"` (default) | Orden alfabético por el nombre completo del servidor (ej. `APIMAN-FASE1` antes que `APIMAN-FASE2`). |
| `"numeric_suffix"` | Orden por el número al final del nombre del servidor, ignorando el prefijo (ej. `QLYMSPROD01` antes que `QBYMSPROD07`, porque compara 01 contra 07; sirve para mezclar prefijos distintos como QBY/QLY en una sola secuencia numérica en vez de separarlos alfabéticamente). |

Cuando una planta tiene más de un servidor, sus bloques de fallas quedan separados
por una línea `====`.

**`camera_order`** — cómo se ordenan entre sí las cámaras dentro de cada ronda de
un `.log` por servidor:

| Valor | Significado |
|---|---|
| `"alpha"` (default) | Orden alfabético por el alias de la cámara. |
| `"numeric_suffix"` | Orden por el número al final del alias, ignorando el prefijo. Soportado por el mismo mecanismo que `servidor_order`, aunque hoy ningún cliente lo necesita. |

En todos los casos, dentro de cada servidor/cámara las fallas o campos quedan
agrupados en este orden fijo: **Puerto 80 → Imagen IA → Imagen cámara →
Configuración → Tiempo de proceso**, y alfabéticamente por alias dentro de cada
grupo.
