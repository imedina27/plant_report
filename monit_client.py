"""Cliente de solo lectura hacia la API de Monit_Servers_V2 (ROADMAP.md, sección 4): temperatura
CPU/GPU promedio del día y uso de disco más reciente, por servidor.

No se modifica ni se importa nada de ese proyecto -- solo se consume su API, ya expuesta en
`http://develop:8000` (el puerto de Postgres no está publicado en su docker-compose, ver
ROADMAP.md). Decidido (21/10/2026): como `/historico` solo da promedio por día (no máximo), el
reporte usa promedio -- "temperatura promedio" en vez de "máxima", sin tocar la infraestructura del
otro proyecto.
"""

from __future__ import annotations

import os
from datetime import date
from functools import lru_cache

import requests
from dotenv import load_dotenv

from reporte_ejecutivo import MetricaServidor, MontajeDisco

load_dotenv()

BASE_URL = os.environ.get("MONIT_API_URL", "http://develop:8000")
_TIMEOUT_S = 10

# Mismos umbrales que backend/main.py de Monit_Servers_V2 (UMBRALES_DEFAULT) -- fallback para un
# servidor sin fila propia en su tabla `umbrales`; normalmente no hace falta, /hardware ya los
# resuelve del lado de Monit_Servers_V2.
_UMBRALES_DEFAULT = {
    "cpu": {"verde_max": 70, "ambar_max": 85},
    "gpu": {"verde_max": 75, "ambar_max": 85},
}


def _calcular_estado(rangos: dict, valor: float) -> str:
    if valor <= rangos["verde_max"]:
        return "verde"
    if valor <= rangos["ambar_max"]:
        return "amarillo"
    return "rojo"


@lru_cache(maxsize=1)
def _servidores_monit() -> dict[str, str]:
    """{NOMBRE_EN_MAYUSCULAS: nombre_real_en_monit} -- los nombres no siempre coinciden en
    mayúsculas/minúsculas entre los dos proyectos (ej. "APIMAN-FASE1" en Plant_Report vs
    "apiman-fase1" en Monit_Servers_V2, visto al revisar su inventario real)."""
    r = requests.get(f"{BASE_URL}/api/servidores", timeout=_TIMEOUT_S)
    r.raise_for_status()
    return {fila["nombre"].upper(): fila["nombre"] for fila in r.json()}


def _nombre_real(servidor: str) -> str | None:
    return _servidores_monit().get(servidor.upper())


def temperaturas_promedio_dia(servidor: str, fecha: date) -> dict[str, MetricaServidor] | None:
    """`{"cpu": MetricaServidor, "gpu": MetricaServidor}` -- `None` si el servidor no existe en
    Monit_Servers_V2 todavía (cobertura incompleta, ver ROADMAP.md). Si existe pero no hay lecturas
    de un componente ese día, esa `MetricaServidor` queda con `valor_c=None` ("Sin datos")."""
    nombre = _nombre_real(servidor)
    if nombre is None:
        return None

    r = requests.get(
        f"{BASE_URL}/api/servidores/{nombre}/historico",
        params={"agrupacion": "dia", "completo": False}, timeout=_TIMEOUT_S,
    )
    r.raise_for_status()
    filas = r.json()

    r_hw = requests.get(f"{BASE_URL}/api/servidores/{nombre}/hardware", timeout=_TIMEOUT_S)
    r_hw.raise_for_status()
    umbrales = r_hw.json().get("umbrales") or _UMBRALES_DEFAULT

    resultado: dict[str, MetricaServidor] = {}
    for componente in ("cpu", "gpu"):
        candidatos = [
            float(f["temperatura_promedio"]) for f in filas
            if f["componente"] == componente and f["periodo"].startswith(fecha.isoformat())
        ]
        if not candidatos:
            resultado[componente] = MetricaServidor(None, None)
            continue
        # El sensor más caliente de ese componente ese día (promediar entre sensores diluiría un
        # núcleo/GPU puntualmente caliente).
        valor = max(candidatos)
        rangos = umbrales.get(componente, _UMBRALES_DEFAULT[componente])
        resultado[componente] = MetricaServidor(valor, _calcular_estado(rangos, valor))
    return resultado


def uso_disco_actual(servidor: str) -> list[MontajeDisco]:
    """Último snapshot por punto de montaje (valor más reciente, no el máximo del día -- decidido
    así en el ROADMAP). `[]` si el servidor no existe en Monit_Servers_V2 o no tiene lecturas."""
    nombre = _nombre_real(servidor)
    if nombre is None:
        return []

    r = requests.get(
        f"{BASE_URL}/api/servidores/{nombre}/disco/historico",
        params={"agrupacion": "hora", "completo": False}, timeout=_TIMEOUT_S,
    )
    r.raise_for_status()
    periodos = r.json()  # ya vienen ordenados por período ascendente
    if not periodos:
        return []
    return [
        MontajeDisco(m["punto_montaje"], m["porcentaje"], m["estado"])
        for m in periodos[-1]["montajes"]
    ]
