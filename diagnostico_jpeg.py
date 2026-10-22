"""Identifica qué imágenes reales disparan avisos de "Corrupt JPEG data" al decodificarlas
(detectado corriendo `backfill_reportes.py` contra octubre/2026) -- libjpeg imprime esos avisos
directo al file descriptor 2 (no a `sys.stderr` de Python), así que hay que capturarlo a ese nivel
para saber de qué archivo vino cada uno.

Uso: pipenv run python diagnostico_jpeg.py
"""

from __future__ import annotations

import os
import tempfile
from datetime import date, timedelta
from pathlib import Path

import cv2
import numpy as np

from image_compare import CHECK_PLANTS_ROOT

FECHA_INICIO = date(2026, 10, 1)
FECHA_FIN = date.today()
_CARPETAS_EXCLUIDAS = {"1- OLD", "Base"}


def _decodificar_con_captura(path: Path) -> str | None:
    data = path.read_bytes()
    fd_original = os.dup(2)
    try:
        with tempfile.TemporaryFile(mode="w+b") as tmp:
            os.dup2(tmp.fileno(), 2)
            try:
                cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
            finally:
                os.dup2(fd_original, 2)
            tmp.seek(0)
            salida = tmp.read().decode("utf-8", errors="replace").strip()
    finally:
        os.close(fd_original)
    return salida or None


def main() -> None:
    encontrados = []
    fecha = FECHA_INICIO
    while fecha <= FECHA_FIN:
        date_str = f"{fecha:%d%m%y}"
        for path in CHECK_PLANTS_ROOT.glob(f"*/*/{date_str}/**/*.jpg"):
            if path.stem.endswith("_ai"):
                continue
            cliente = path.relative_to(CHECK_PLANTS_ROOT).parts[0]
            if cliente in _CARPETAS_EXCLUIDAS:
                continue
            aviso = _decodificar_con_captura(path)
            if aviso:
                _cliente, _mes, _fecha, planta, servidor = path.relative_to(CHECK_PLANTS_ROOT).parts[:5]
                encontrados.append((fecha, _cliente, planta, servidor, path.stem, aviso))
        fecha += timedelta(days=1)

    print(f"Imágenes con aviso de decodificación: {len(encontrados)}\n")
    for fecha, cliente, planta, servidor, camara, aviso in encontrados:
        print(f"{fecha:%d/%m/%Y}  {cliente}/{planta}/{servidor}/{camara}  -- {aviso}")


if __name__ == "__main__":
    main()
