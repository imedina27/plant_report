"""Genera un PDF de muestra del reporte ejecutivo (Fase 4) con datos inventados -- para revisar el
layout antes de conectarlo a la base de datos real y a la API de Monit_Servers_V2.

Uso: pipenv run python scripts/mock_reporte_ejecutivo.py [ruta_salida.pdf]
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from reporte_ejecutivo import CamaraFalla, MetricaServidor, MontajeDisco, ResumenServidor, construir_pdf

SERVIDORES = [
    # Servidor sano: todo OK, sin detalle (no genera hoja propia).
    ResumenServidor(
        nombre="QLYMSPROD01", planta="ZACATECAS",
        cpu=MetricaServidor(52.3, "verde"), gpu=MetricaServidor(61.0, "verde"),
        discos=[MontajeDisco("/", 42.0, "verde"), MontajeDisco("/home", 55.0, "verde")],
        camaras_totales=12, camaras_ok=12, camaras_no_concluyentes=0, fallas=[],
    ),
    # Servidor con fallas mixtas + disco en ambar y temperatura en rojo. 6 OK + 1 no concluyente
    # (ambar de 1-2 días, no cuenta como falla todavía) + 4 con falla = 11 totales.
    ResumenServidor(
        nombre="QLYMSPROD03", planta="APAN",
        cpu=MetricaServidor(88.4, "rojo"), gpu=MetricaServidor(69.2, "verde"),
        discos=[MontajeDisco("/", 76.0, "amarillo"), MontajeDisco("/data", 91.0, "rojo")],
        camaras_totales=11, camaras_ok=6, camaras_no_concluyentes=1,
        fallas=[
            CamaraFalla("AD1l1", "rojo", "Cámara movida (confirmado)", "Confirmado por un humano: la cámara se movió"),
            CamaraFalla("SP-TE01", "morado", "Pendiente de revisión", "Desplazamiento por encima del umbral"),
            CamaraFalla("ENT1-Op01", "base_desactualizada", "Base de imágenes desactualizada", "Pendiente de que alguien suba una imagen limpia (ventana_bases.py)"),
            CamaraFalla("B07", "rojo", "Cámara sin respuesta", "Puerto 80 Timed out [111]"),
        ],
    ),
    # Servidor sin datos de monitoreo todavia (no esta en Monit_Servers_V2).
    ResumenServidor(
        nombre="QLYMSPROD05", planta="TOCANCIPA",
        cpu=None, gpu=None, discos=[],
        camaras_totales=9, camaras_ok=8, camaras_no_concluyentes=0,
        fallas=[CamaraFalla("EVP", "rojo", "Cámara sin respuesta", "Puerto 80 Service Unavailable [503]")],
    ),
]


def main() -> None:
    ruta_salida = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("mock_reporte_ejecutivo.pdf")
    construir_pdf("AbInBev", date(2026, 10, 21), SERVIDORES, ruta_salida)
    print(f"OK -- generado en {ruta_salida.resolve()}")


if __name__ == "__main__":
    main()
