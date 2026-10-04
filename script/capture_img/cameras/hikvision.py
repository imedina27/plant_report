"""Captura una imagen de una cámara HIKVISION (ROADMAP.md, sección 2.8).

Mismo endpoint y autenticación que `Check_Cameras/conf/cameras/hikvision.py`
(`HikvCamImage`) y que `Test/Camara_Fisica/capturar.py` en este proyecto.
"""

from __future__ import annotations

import requests

TIMEOUT = 15


def capturar(ip: str, usuario: str, password: str) -> bytes:
    url = f"http://{ip}/ISAPI/Streaming/channels/1/picture"
    auth = requests.auth.HTTPDigestAuth(usuario, password)
    respuesta = requests.get(url, auth=auth, timeout=TIMEOUT)
    respuesta.raise_for_status()
    return respuesta.content
