"""Bootstrap del historial de imágenes por cámara (ROADMAP.md, 26/10/2026 -- paso hacia una base
de referencia por mediana en vez de la foto de un solo día).

Para cada cámara, si su historial en `IMAGE_HISTORY_ROOT` todavía no tiene las
`N_DIAS_MEDIANA_BASE` imágenes necesarias, lo completa buscando hacia atrás en todo el histórico
real de `CHECK_PLANTS_ROOT` -- evita esperar `N_DIAS_MEDIANA_BASE` días reales de corridas
normales para poder construir la primera mediana.

No sobrescribe nada que ya esté guardado -- solo agrega lo que falte, con los días más recientes
del archivo primero. Descarta imágenes corruptas o de resolución distinta a la más reciente válida
de esa cámara, para no mezclar fotos de antes de un cambio de cámara/lente.

Uso: pipenv run python scripts/bootstrap_image_history.py
"""

from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from comparacion.image_compare import (
    CHECK_PLANTS_ROOT,
    N_DIAS_MEDIANA_BASE,
    fechas_en_historial,
    guardar_historial_imagen,
    historial_path,
    imread_unicode,
)

_CARPETAS_EXCLUIDAS = {"1- OLD", "Base"}


def _indice_imagenes() -> dict[tuple[str, str, str, str], dict[date, Path]]:
    """`{(cliente, planta, servidor, camara): {fecha: ruta_jpg}}` -- todo el histórico disponible
    bajo `CHECK_PLANTS_ROOT` (mismo criterio que `bootstrap_image_base.py`)."""
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
    indice = _indice_imagenes()

    completadas = ya_tenian = sin_suficiente = 0

    for (cliente, planta, servidor, camara), fechas in sorted(indice.items()):
        existentes = fechas_en_historial(cliente, planta, servidor, camara)
        faltan = N_DIAS_MEDIANA_BASE - len(existentes)
        if faltan <= 0:
            ya_tenian += 1
            continue

        # La resolución de la imagen ya guardada más reciente (o, si no hay ninguna, la primera
        # válida que se encuentre) define qué cuenta como "misma cámara" -- ver docstring.
        resolucion_ref = None
        if existentes:
            ref = imread_unicode(historial_path(cliente, planta, servidor, camara, max(existentes)))
            resolucion_ref = ref.shape if ref is not None else None

        candidatos = sorted(fechas.items(), reverse=True)  # más reciente primero
        agregadas = 0
        for fecha, origen in candidatos:
            if agregadas >= faltan:
                break
            if fecha in existentes:
                continue
            img = imread_unicode(origen)
            if img is None:
                continue
            if resolucion_ref is None:
                resolucion_ref = img.shape
            elif img.shape != resolucion_ref:
                continue
            guardar_historial_imagen(cliente, planta, servidor, camara, origen, fecha)
            agregadas += 1

        total_final = len(existentes) + agregadas
        if total_final >= N_DIAS_MEDIANA_BASE:
            completadas += 1
        else:
            sin_suficiente += 1
            print(f"  (solo {total_final}/{N_DIAS_MEDIANA_BASE} días válidos en el archivo) "
                  f"{cliente}/{planta}/{servidor}/{camara}")

    print(f"\nHistorial completado a {N_DIAS_MEDIANA_BASE} días: {completadas}")
    print(f"Ya tenían suficiente historial (sin tocar): {ya_tenian}")
    print(f"Archivo insuficiente para completar {N_DIAS_MEDIANA_BASE} días: {sin_suficiente}")


if __name__ == "__main__":
    main()
