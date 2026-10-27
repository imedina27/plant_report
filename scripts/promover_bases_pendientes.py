"""Promoción inicial, de una sola vez, de las bases ya listas a mediana (ROADMAP.md, 26/10/2026).

A diferencia del flujo normal (que solo promueve una base provisional tras un reemplazo manual en
`ui/ventana_bases.py`), este script recorre **todas** las cámaras encontradas en `IMAGE_BASE_ROOT`
y promueve cualquiera que ya tenga las `N_DIAS_MEDIANA_BASE` completas en su historial -- pensado
para aprovechar de una vez el trabajo de `bootstrap_image_history.py`, sin esperar a que a cada
cámara le toque pasar por un reemplazo manual.

No toca la base de datos (no hay "promoción pendiente" que apagar aquí -- estas cámaras nunca
tuvieron `base_reemplazada_el` puesto). Es seguro volver a correrlo: una cámara ya promovida sigue
teniendo su historial completo, así que se promovería otra vez con una mediana que debería salir
prácticamente igual (una foto más reciente puede haber entrado a la ventana rotatoria).

Uso: pipenv run python scripts/promover_bases_pendientes.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from comparacion.image_compare import IMAGE_BASE_ROOT, promover_base_a_mediana


def _camaras_con_base() -> list[tuple[str, str, str, str]]:
    camaras = []
    for path in IMAGE_BASE_ROOT.glob("*/*/*/*.jpg"):
        cliente, planta, servidor = path.relative_to(IMAGE_BASE_ROOT).parts[:3]
        camaras.append((cliente, planta, servidor, path.stem))
    return camaras


def main() -> None:
    promovidas = sin_suficiente = 0

    for cliente, planta, servidor, camara in sorted(_camaras_con_base()):
        if promover_base_a_mediana(cliente, planta, servidor, camara):
            promovidas += 1
        else:
            sin_suficiente += 1

    print(f"Bases promovidas a mediana: {promovidas}")
    print(f"Sin suficiente historial todavía: {sin_suficiente}")


if __name__ == "__main__":
    main()
