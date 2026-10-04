"""Registro de marcas soportadas para `captura.py` (ROADMAP.md, sección 2.8).

Agregar una marca nueva es: un archivo `cameras/[marca].py` con una función
`capturar(ip, usuario, password) -> bytes`, más una línea aquí -- no hay que tocar
`captura.py` ni las demás marcas.
"""

from __future__ import annotations

from . import axis, dahua, hikvision, vivotek

CAPTURA_POR_MARCA = {
    "AXIS": axis.capturar,
    "DAHUA": dahua.capturar,
    "HIKVISION": hikvision.capturar,
    "VIVOTEK": vivotek.capturar,
}
