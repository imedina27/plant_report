"""Vista previa de la ventana de revisión con datos e imágenes reales, SIN tocar la base de datos
ni disparar una corrida completa de `main.py` (ROADMAP.md, 26/10/2026).

Busca una cámara real que ya tenga base + los `N_DIAS_MEDIANA_BASE` días de historial completos
(para que nitidez y día anterior salgan con números reales, no "N/D"), le aplica un desplazamiento
sintético a su propia base -- en memoria, sin guardar nada -- para forzar un `REVISAR` con el
diagnóstico más completo posible (el caso que más estira el layout de la ventana), y lo arma con
`main._formatear_diagnostico()`: el mismo texto, letra por letra, que vería un usuario real.

Este script nunca importa `persistencia.db` -- no hay manera de que toque la base de datos. El
único archivo que escribe es una copia temporal de la imagen sintética (carpeta temporal del
sistema), que se borra al cerrar la ventana.

Uso: pipenv run python -m scripts.preview_ventana_revision
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import cv2
import numpy as np

from comparacion.image_compare import (
    IMAGE_HISTORY_ROOT,
    N_DIAS_MEDIANA_BASE,
    base_path,
    evaluar_dia_anterior,
    evaluar_nitidez,
    evaluar_par,
    evaluar_salud_imagen,
    imread_unicode,
    imwrite_unicode,
)
from main import _formatear_diagnostico
from ui.ventana_revision import VentanaRevision


def _buscar_camara_con_historial_completo() -> tuple[str, str, str, str]:
    for carpeta in IMAGE_HISTORY_ROOT.glob("*/*/*/*"):
        if not carpeta.is_dir() or len(list(carpeta.glob("*.jpg"))) < N_DIAS_MEDIANA_BASE:
            continue
        camara, servidor, planta, cliente = (
            carpeta.name, carpeta.parent.name, carpeta.parent.parent.name,
            carpeta.parent.parent.parent.name,
        )
        if base_path(cliente, planta, servidor, camara).exists():
            return cliente, planta, servidor, camara
    raise SystemExit(
        "No se encontró ninguna cámara real con base + historial completo para la vista previa."
    )


def main() -> None:
    cliente, planta, servidor, camara = _buscar_camara_con_historial_completo()
    print(f"Cámara usada para la vista previa: {cliente}/{planta}/{servidor}/{camara}")

    ruta_base = base_path(cliente, planta, servidor, camara)
    base = imread_unicode(ruta_base)

    # Desplazamiento sintético de 40px -- en memoria, nunca se guarda como base ni como historial
    # -- para forzar un REVISAR con el diagnóstico más largo posible (el caso que más estira el
    # layout: motivo + ORB/Fase + ORB detallado + nitidez + salud + día anterior).
    alto, ancho = base.shape[:2]
    desplazamiento = np.array([[1, 0, 40], [0, 1, 0]], dtype=np.float32)
    actual_sintetica = cv2.warpAffine(base, desplazamiento, (ancho, alto))

    resultado = evaluar_par(base, actual_sintetica, None)
    resultado.update(evaluar_nitidez(cliente, planta, servidor, camara, actual_sintetica))
    resultado.update(evaluar_salud_imagen(actual_sintetica))
    resultado.update(evaluar_dia_anterior(cliente, planta, servidor, camara, actual_sintetica))

    diagnostico = _formatear_diagnostico(resultado)
    print("\n--- Diagnóstico que se mostraría en la ventana ---")
    print(diagnostico)
    print("---------------------------------------------------\n")

    ruta_actual_temp = Path(tempfile.gettempdir()) / "plant_report_preview_actual.jpg"
    imwrite_unicode(ruta_actual_temp, actual_sintetica)
    try:
        ventana = VentanaRevision()
        titulo = f"{cliente}/{planta}/{servidor}/{camara} -- VISTA PREVIA (desplazamiento sintético)"
        accion, observacion = ventana.pedir_revision(titulo, diagnostico, ruta_base, ruta_actual_temp)
        print(f"Botón elegido: {accion!r}  Observación: {observacion!r}")
        ventana.cerrar()
    finally:
        ruta_actual_temp.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
