"""Captura una imagen de una cámara AXIS (ROADMAP.md, sección 2.8).

Mismo endpoint y autenticación que ya usa el programa de revisión en producción
(`Check_Cameras/conf/cameras/axis.py`, función `AxisCamImage`) -- aquí sin proxy,
sesión compartida ni logging a archivo, porque este script hace una sola captura
manual, no un escaneo masivo de cientos de cámaras.
"""

from __future__ import annotations

import requests

TIMEOUT = 15


def capturar(ip: str, usuario: str, password: str) -> bytes:
    url = f"http://{ip}/axis-cgi/jpg/image.cgi?camera=1"
    auth = requests.auth.HTTPDigestAuth(usuario, password)
    respuesta = requests.get(url, auth=auth, timeout=TIMEOUT)
    respuesta.raise_for_status()
    return respuesta.content
