"""Bootstrap de las bases de imagen (Fase 2, ROADMAP.md).

Para cada cámara encontrada en `CHECK_PLANTS_ROOT`, copia su `.jpg` de hoy (o, si falta, el más
reciente de un día anterior) a `IMAGE_BASE_ROOT` -- mismo criterio que `bootstrap_config_base.py`.

No sobrescribe una base que ya exista. No importa si la imagen tiene un camión/montacargas/persona
en cuadro (Experimento 3, Fase 2: el algoritmo lo tolera salvo que el objeto llene casi todo el
cuadro) -- se van mejorando después a mano, cámara por cámara, con `ventana_bases.py` cuando
convenga. Excluye `1- OLD`, `Base` y las imágenes `_ai` (ya procesadas, no la cruda de cámara).

Uso: pipenv run python bootstrap_image_base.py
"""

from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from comparacion.image_compare import CHECK_PLANTS_ROOT, base_path, save_base

_CARPETAS_EXCLUIDAS = {"1- OLD", "Base"}


def _indice_imagenes() -> dict[tuple[str, str, str, str], dict[date, Path]]:
    """`{(cliente, planta, servidor, camara): {fecha: ruta_jpg}}` -- todo el histórico disponible
    bajo `CHECK_PLANTS_ROOT`."""
    indice: dict[tuple[str, str, str, str], dict[date, Path]] = {}
    for path in CHECK_PLANTS_ROOT.glob("*/*/*/**/*.jpg"):
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
    indice = _indice_imagenes()

    creadas_hoy = creadas_dia_anterior = ya_existian = 0
    sin_ninguna_imagen: list[tuple[str, str, str, str]] = []

    for (cliente, planta, servidor, camara), fechas in sorted(indice.items()):
        if base_path(cliente, planta, servidor, camara).exists():
            ya_existian += 1
            continue

        if hoy in fechas:
            origen, fecha_usada = fechas[hoy], hoy
        else:
            anteriores = [f for f in fechas if f < hoy]
            if not anteriores:
                sin_ninguna_imagen.append((cliente, planta, servidor, camara))
                continue
            fecha_usada = max(anteriores)
            origen = fechas[fecha_usada]

        save_base(cliente, planta, servidor, camara, origen)
        if fecha_usada == hoy:
            creadas_hoy += 1
        else:
            creadas_dia_anterior += 1
            print(f"  (usando {fecha_usada:%d/%m/%y}, no había de hoy) {cliente}/{planta}/{servidor}/{camara}")

    print(f"\nBases creadas con el .jpg de hoy: {creadas_hoy}")
    print(f"Bases creadas con el .jpg de un día anterior: {creadas_dia_anterior}")
    print(f"Ya tenían base (sin tocar): {ya_existian}")
    print(f"Sin ninguna imagen en todo el histórico ({len(sin_ninguna_imagen)}):")
    for cliente, planta, servidor, camara in sin_ninguna_imagen:
        print(f"  - {cliente}/{planta}/{servidor}/{camara}")


if __name__ == "__main__":
    main()
