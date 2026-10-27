"""Bootstrap de las bases de configuración (Fase 1, ROADMAP.md).

Para cada cámara encontrada en `CHECK_PLANTS_ROOT`, copia su `.json` de hoy (o, si falta, el más
reciente de un día anterior) a `CONFIG_BASE_ROOT` -- de una sola vez, en vez de depender de que cada
cámara genere su base sola la primera vez que corra `main.py` sobre ella.

No sobrescribe una base que ya exista (se asume curada/válida y se deja igual). Excluye `1- OLD`
(histórico 2025, estructura de carpetas distinta -- ver ROADMAP.md) y `Base` (donde ya viven
`CONFIG_BASE_ROOT`/`IMAGE_BASE_ROOT`, ambas dentro de `CHECK_PLANTS_ROOT`).

Uso: pipenv run python bootstrap_config_base.py
"""

from __future__ import annotations

import shutil
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from comparacion.config_compare import CHECK_PLANTS_ROOT, base_path

_CARPETAS_EXCLUIDAS = {"1- OLD", "Base"}


def _indice_configs() -> dict[tuple[str, str, str, str], dict[date, Path]]:
    """`{(cliente, planta, servidor, camara): {fecha: ruta_json}}` -- todo el histórico disponible
    bajo `CHECK_PLANTS_ROOT`."""
    indice: dict[tuple[str, str, str, str], dict[date, Path]] = {}
    for path in CHECK_PLANTS_ROOT.glob("*/*/*/**/*.json"):
        if path.stem.endswith("_ai"):
            continue
        cliente, _mes, fecha_str, planta, servidor = path.relative_to(CHECK_PLANTS_ROOT).parts[:5]
        if cliente in _CARPETAS_EXCLUIDAS:
            continue
        try:
            fecha = datetime.strptime(fecha_str, "%d%m%y").date()
        except ValueError:
            continue  # carpeta con formato de fecha inesperado -- se ignora, no se adivina
        camara = path.stem
        indice.setdefault((cliente, planta, servidor, camara), {})[fecha] = path
    return indice


def main() -> None:
    hoy = date.today()
    indice = _indice_configs()

    creadas_hoy = creadas_dia_anterior = ya_existian = 0
    sin_ningun_json: list[tuple[str, str, str, str]] = []

    for (cliente, planta, servidor, camara), fechas in sorted(indice.items()):
        destino = base_path(cliente, planta, servidor, camara)
        if destino.exists():
            ya_existian += 1
            continue

        if hoy in fechas:
            origen, fecha_usada = fechas[hoy], hoy
        else:
            anteriores = [f for f in fechas if f < hoy]
            if not anteriores:
                sin_ningun_json.append((cliente, planta, servidor, camara))
                continue
            fecha_usada = max(anteriores)
            origen = fechas[fecha_usada]

        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origen, destino)
        if fecha_usada == hoy:
            creadas_hoy += 1
        else:
            creadas_dia_anterior += 1
            print(f"  (usando {fecha_usada:%d/%m/%y}, no había de hoy) {cliente}/{planta}/{servidor}/{camara}")

    print(f"\nBases creadas con el .json de hoy: {creadas_hoy}")
    print(f"Bases creadas con el .json de un día anterior: {creadas_dia_anterior}")
    print(f"Ya tenían base (sin tocar): {ya_existian}")
    print(f"Sin ningún .json en todo el histórico ({len(sin_ningun_json)}):")
    for cliente, planta, servidor, camara in sin_ningun_json:
        print(f"  - {cliente}/{planta}/{servidor}/{camara}")


if __name__ == "__main__":
    main()
