"""Parsea el `.log` por servidor (ver ROADMAP.md, "Estructura de datos") para saber, por cámara,
si el programa externo de revisión logró capturarla ese día y, si no, por qué.

Es la fuente de verdad de qué cámaras se intentaron procesar ese día -- incluidas las que fallaron
por completo (ej. timeout de puerto) y por lo tanto nunca llegan a tener `.jpg`/`.json` (ver
ROADMAP.md, sección 3: sin esto, esas cámaras eran invisibles para el resto del programa).
"""

from __future__ import annotations

import re
from pathlib import Path

_RE_IP = re.compile(
    r"^\[(?P<hora>\d{2}:\d{2}:\d{2})\]\s+(?:INFO|ERROR)\s+(?P<camara>\S+)\s+IP:\s*(?P<ip>\S+)\s*$"
)
_RE_CAMPO = re.compile(
    r"^\[(?P<hora>\d{2}:\d{2}:\d{2})\]\s+(?P<nivel>INFO|ERROR)\s+(?P<camara>\S+):\s*(?P<resto>.+?)\s*$"
)
_RE_TIEMPO = re.compile(r"Tiempo de proceso\s+([\d.]+)s", re.IGNORECASE)
_RE_PUERTO_IA = re.compile(
    r"^\[(?P<hora>\d{2}:\d{2}:\d{2})\]\s+INFO\s+Puerto IA configurado\s+(?P<puerto>\d+)\s*$"
)
_RE_YAML = re.compile(
    r"^\[(?P<hora>\d{2}:\d{2}:\d{2})\]\s+(?P<nivel>INFO|ERROR)\s+YAML\s+(?P<resto>.+?)\s*$"
)


def _nueva_entrada() -> dict:
    return {"ip": None, "estado": "OK", "motivo": None, "tiempo_proceso": None}


def parsear_log_servidor(log_path: Path) -> dict[str, dict]:
    """Regresa `{camara: {"ip", "estado" ("OK"|"ERROR"), "motivo", "tiempo_proceso"}}`.

    Tolera varias rondas en un mismo archivo y ambos finales de línea (LF/CRLF, ver nota en
    ROADMAP.md). Si una cámara nunca tiene una línea `ERROR`, su estado queda "OK"; se guarda el
    primer error visto (los pasos posteriores de esa misma cámara se siguen registrando igual,
    como `Imagen cámara` fallando sin que `Configuración` deje de intentarse después).
    """
    if not log_path.exists():
        return {}

    data = log_path.read_bytes()
    try:
        texto = data.decode("utf-8")
    except UnicodeDecodeError:
        # Algunos .log (ej. API-MANZANILLO) no vienen en UTF-8 sino en cp1252 -- se ve en los
        # acentos de "Imagen cámara"/"Configuración" en las líneas ERROR.
        texto = data.decode("cp1252")

    camaras: dict[str, dict] = {}
    for linea in texto.splitlines():
        linea = linea.strip()

        m_ip = _RE_IP.match(linea)
        if m_ip:
            camaras.setdefault(m_ip["camara"], _nueva_entrada())["ip"] = m_ip["ip"]
            continue

        m_campo = _RE_CAMPO.match(linea)
        if not m_campo:
            continue

        camara, nivel, resto = m_campo["camara"], m_campo["nivel"], m_campo["resto"]
        info = camaras.setdefault(camara, _nueva_entrada())

        m_tiempo = _RE_TIEMPO.search(resto)
        if m_tiempo:
            info["tiempo_proceso"] = float(m_tiempo.group(1))
            continue

        if nivel == "ERROR" and info["estado"] == "OK":
            info["estado"] = "ERROR"
            info["motivo"] = resto

    return camaras


def parsear_servicios_ia_servidor(log_path: Path) -> list[dict]:
    """Regresa `[{"puerto", "estado" ("ok"|"caido"), "motivo"}, ...]`, uno por cada puerto de
    servicio de IA configurado en ese servidor (ROADMAP.md, 27/10/2026) -- un mismo servidor puede
    tener más de uno (ej. Api_Manzanillo, con hasta 4).

    Depende de que el programa externo imprima `Puerto IA configurado <N>` justo antes de intentar
    leer el YAML de ese puerto: antes de ese cambio, una lectura fallida no dejaba ningún rastro del
    puerto en el log, y no había forma de saber a cuál de varios puertos atribuir la falla.
    """
    if not log_path.exists():
        return []

    data = log_path.read_bytes()
    try:
        texto = data.decode("utf-8")
    except UnicodeDecodeError:
        texto = data.decode("cp1252")

    servicios: list[dict] = []
    puerto_pendiente: int | None = None
    for linea in texto.splitlines():
        linea = linea.strip()

        m_puerto = _RE_PUERTO_IA.match(linea)
        if m_puerto:
            puerto_pendiente = int(m_puerto["puerto"])
            continue

        m_yaml = _RE_YAML.match(linea)
        if m_yaml and puerto_pendiente is not None:
            servicios.append({
                "puerto": puerto_pendiente,
                "estado": "ok" if m_yaml["nivel"] == "INFO" else "caido",
                "motivo": f"YAML {m_yaml['resto']}",
            })
            puerto_pendiente = None

    return servicios
