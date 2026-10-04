"""Captura una imagen de una cámara VIVOTEK (ROADMAP.md, sección 2.8).

A diferencia de las otras 3 marcas, VIVOTEK usa autenticación Basic (no Digest) para
la imagen, y no hay un único endpoint confiable entre modelos/generaciones -- se
prueban varios candidatos en orden hasta que uno responda, igual que en producción
(`Check_Cameras/conf/cameras/vivotek.py`, `VivoCamImage`).
"""

from __future__ import annotations

import requests

TIMEOUT = 15

_RUTAS_CANDIDATAS = [
    "/cgi-bin/viewer/video.jpg",
    "/cgi-bin/viewer/video.jpg?channel=0",
    "/video.jpg",
    "/cgi-bin/jpeg.cgi",
    "/cgi-bin/viewer/snapshot.cgi",
]


def capturar(ip: str, usuario: str, password: str) -> bytes:
    auth = requests.auth.HTTPBasicAuth(usuario, password)
    ultimo_error: Exception | None = None
    for ruta in _RUTAS_CANDIDATAS:
        try:
            respuesta = requests.get(f"http://{ip}{ruta}", auth=auth, timeout=TIMEOUT)
            respuesta.raise_for_status()
            return respuesta.content
        except requests.exceptions.HTTPError as error:
            ultimo_error = error
            continue
    raise ConnectionError(f"Ningún endpoint de imagen conocido respondió en {ip}") from ultimo_error
