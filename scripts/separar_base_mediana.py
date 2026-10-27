"""Migración de una sola vez: separa la base "para mostrar" (foto real de un solo día) de la base
"para calcular" (mediana por píxel) -- ROADMAP.md, 27/10/2026.

Hasta ahora `promover_base_a_mediana()` sobrescribía directamente `IMAGE_BASE_ROOT`, así que
cualquier cámara ya promovida (ver `promover_bases_pendientes.py`, que corrió sobre toda la base
de datos) tiene ahí una mezcla por píxel de varios días -- estadísticamente válida para medir
desplazamiento, pero confusa para un humano (puede mostrar "fantasmas" de vehículos/personas que
solo estuvieron presentes algunos de esos días; ver conversación del 27/10/2026).

Este script, para cada cámara con base existente:
  1. Copia tal cual lo que hoy esté en `IMAGE_BASE_ROOT` hacia `IMAGE_BASE_MEDIANA_ROOT` -- sea la
     mediana ya promovida o todavía la foto original, el cálculo sigue exactamente igual que antes
     (mismos bytes), cero riesgo para la comparación.
  2. Busca, en todo el mes en curso de `CHECK_PLANTS_ROOT` **excepto hoy** (hoy llueve en Zacatecas
     -- piso mojado, muchos reflejos -- y en general conviene no depender del día más reciente para
     esto), la foto más "limpia" de esa cámara según un detector de objetos preentrenado (YOLOv8n,
     clases persona/bicicleta/auto/moto/camión/autobús) y la escribe en `IMAGE_BASE_ROOT`, para que
     la ventana de revisión y el PDF vuelvan a mostrar una foto real sin editar.

Si ninguna foto del mes queda sin detecciones, usa la que tenga menos (no es un error -- hay
cámaras con tráfico casi constante). Si la cámara no tiene ninguna foto utilizable ese mes, no toca
su `IMAGE_BASE_ROOT` (sigue como estaba).

Con `--dry-run` no escribe nada, solo reporta qué haría -- úsalo primero.
Con `--client` y/o `--camera` limita la migración a una sola cámara, para probar antes de
correrlo sobre las ~265 cámaras completas.

Uso: pipenv run python scripts/separar_base_mediana.py --dry-run
     pipenv run python scripts/separar_base_mediana.py --client AbInBev --camera BX5 --dry-run
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from comparacion.image_compare import (
    CHECK_PLANTS_ROOT,
    IMAGE_BASE_ROOT,
    base_mediana_path,
    base_path,
)

_CARPETAS_EXCLUIDAS = {"1- OLD", "Base"}

# Clases COCO que cuentan como "no limpia" -- ver nombres en https://docs.ultralytics.com/datasets/detect/coco/
_CLASES_SUCIAS = {0, 1, 2, 3, 5, 7}  # person, bicycle, car, motorcycle, bus, truck
_CONFIANZA_MINIMA = 0.35


def _camaras_con_base() -> list[tuple[str, str, str, str]]:
    camaras = []
    for path in IMAGE_BASE_ROOT.glob("*/*/*/*.jpg"):
        cliente, planta, servidor = path.relative_to(IMAGE_BASE_ROOT).parts[:3]
        camaras.append((cliente, planta, servidor, path.stem))
    return camaras


def _candidatas_del_mes(hoy: date) -> dict[tuple[str, str, str, str], list[Path]]:
    """`{(cliente, planta, servidor, camara): [rutas]}` -- fotos del mes en curso de `hoy`,
    excluyéndolo a él, más reciente primero."""
    indice: dict[tuple[str, str, str, str], list[tuple[date, Path]]] = {}
    for path in CHECK_PLANTS_ROOT.glob("*/*/*/**/*.jpg"):
        if path.stem.endswith("_ai"):
            continue
        cliente, _mes, fecha_str, planta, servidor = path.relative_to(CHECK_PLANTS_ROOT).parts[:5]
        if cliente in _CARPETAS_EXCLUIDAS:
            continue
        try:
            fecha = datetime.strptime(fecha_str, "%d%m%y").date()
        except ValueError:
            continue
        if fecha == hoy or fecha.year != hoy.year or fecha.month != hoy.month:
            continue
        camara = path.stem
        indice.setdefault((cliente, planta, servidor, camara), []).append((fecha, path))

    return {
        clave: [p for _f, p in sorted(fechas, reverse=True)]
        for clave, fechas in indice.items()
    }


def _elegir_candidata_limpia(modelo, candidatas: list[Path]) -> tuple[Path | None, int]:
    """Regresa `(ruta_elegida, detecciones_de_la_elegida)` -- la primera sin detecciones "sucias",
    o si ninguna califica, la de menos detecciones. `(None, 0)` si no hay candidatas."""
    if not candidatas:
        return None, 0

    mejor_ruta, mejor_conteo = None, None
    for ruta in candidatas:
        resultado = modelo.predict(str(ruta), verbose=False, conf=_CONFIANZA_MINIMA)[0]
        conteo = sum(1 for clase_id in resultado.boxes.cls.tolist() if int(clase_id) in _CLASES_SUCIAS)
        if conteo == 0:
            return ruta, 0
        if mejor_conteo is None or conteo < mejor_conteo:
            mejor_ruta, mejor_conteo = ruta, conteo

    return mejor_ruta, mejor_conteo


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Separa la base 'para mostrar' de la base 'para calcular' -- ver docstring.",
    )
    parser.add_argument("--dry-run", action="store_true", help="No escribe nada, solo reporta.")
    parser.add_argument("--client", help="Limita la migración a este cliente.")
    parser.add_argument("--camera", help="Limita la migración a esta cámara (nombre exacto).")
    args = parser.parse_args()

    from ultralytics import YOLO
    # "n" (nano) falló en cámaras de muelle con la cámara muy cerca del camión (grilla llenando
    # casi todo el cuadro): a conf=0.05 no detectó nada; "m" sí lo reconoce (como "car", no
    # "truck", pero esa clase también está en _CLASES_SUCIAS) -- ver conversación 27/10/2026.
    modelo = YOLO("yolov8m.pt")

    hoy = date.today()
    candidatas_por_camara = _candidatas_del_mes(hoy)

    camaras = _camaras_con_base()
    if args.client:
        camaras = [c for c in camaras if c[0] == args.client]
    if args.camera:
        camaras = [c for c in camaras if c[3] == args.camera]

    movidas = sin_candidatas = elegidas_limpias = elegidas_con_detecciones = 0

    for cliente, planta, servidor, camara in sorted(camaras):
        candidatas = candidatas_por_camara.get((cliente, planta, servidor, camara), [])
        if not candidatas:
            sin_candidatas += 1
            print(f"  (sin fotos este mes, aparte de hoy) {cliente}/{planta}/{servidor}/{camara}")
            continue

        elegida, detecciones = _elegir_candidata_limpia(modelo, candidatas)
        if elegida is None:
            sin_candidatas += 1
            continue

        etiqueta = "limpia" if detecciones == 0 else f"{detecciones} detección(es) (sin otra opción)"
        fecha_elegida = elegida.relative_to(CHECK_PLANTS_ROOT).parts[2]  # el nombre de archivo
        # siempre es "<camara>.jpg" -- lo que cambia día a día es la carpeta de fecha, no el nombre.
        print(f"{cliente}/{planta}/{servidor}/{camara}: {fecha_elegida} [{etiqueta}]")

        if not args.dry_run:
            ruta_original = base_path(cliente, planta, servidor, camara)
            ruta_mediana = base_mediana_path(cliente, planta, servidor, camara)
            if not ruta_mediana.exists():
                # Si ya se había separado antes (ej. al volver a correr esto con un modelo mejor),
                # no hay que tocar la mediana de nuevo -- solo se repite la elección de display.
                ruta_mediana.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ruta_original, ruta_mediana)
            shutil.copyfile(elegida, ruta_original)

        movidas += 1
        if detecciones == 0:
            elegidas_limpias += 1
        else:
            elegidas_con_detecciones += 1

    print(f"\nCámaras migradas: {movidas} (limpias: {elegidas_limpias}, "
          f"con alguna detección por falta de opción: {elegidas_con_detecciones})")
    print(f"Sin fotos utilizables este mes (sin tocar): {sin_candidatas}")
    if args.dry_run:
        print("\n(--dry-run: no se escribió nada)")


if __name__ == "__main__":
    main()
