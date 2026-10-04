"""Captura una imagen de una cámara DAHUA (ROADMAP.md, sección 2.8).

Mismo endpoint y autenticación que `Check_Cameras/conf/cameras/dahua.py`
(`DahuaCamImage`) -- probado y en uso real en producción (confirmado por el usuario
03/10/2026), a diferencia del dump de configuración de esta marca (Fase 1), que
sigue pendiente de un ejemplo real.
"""

from __future__ import annotations

import requests

TIMEOUT = 15

_RUTAS_CANDIDATAS = [
    "/cgi-bin/snapshot.cgi?channel=1",
    "/cgi-bin/snapshot.cgi?chn=1",
    "/cgi-bin/snapshot.cgi",
]


def capturar(ip: str, usuario: str, password: str) -> bytes:
    auth = requests.auth.HTTPDigestAuth(usuario, password)
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
