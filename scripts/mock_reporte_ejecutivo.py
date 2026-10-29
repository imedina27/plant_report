"""Genera un PDF de muestra del reporte ejecutivo (Fase 4) con datos inventados -- para revisar el
layout antes de conectarlo a la base de datos real y a la API de Monit_Servers_V2.

Uso: pipenv run python scripts/mock_reporte_ejecutivo.py [ruta_salida.pdf]
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from comparacion.image_compare import base_path
from reporte.reporte_ejecutivo import CamaraFalla, MetricaServidor, MontajeDisco, ResumenServidor, construir_pdf

# Par real (base/actual) para mostrar cómo se ve "Cámara movida" con sus 2 fotos -- no son fotos de
# una cámara realmente movida, es solo para probar el layout con archivos reales (ROADMAP.md, 28/10/2026).
_RUTA_BASE_EJEMPLO = base_path("AbInBev", "ZACATECAS", "QLYMSPROD01", "A1p")
_RUTA_ACTUAL_EJEMPLO = Path(
    r"D:\Imágenes\Quantum Labs\Check Plants\AbInBev\10- Octubre\281026\ZACATECAS\QLYMSPROD01\A1p.jpg"
)

SERVIDORES = [
    # Servidor sano: todo OK, sin detalle (no genera hoja propia). Vision-Stream con 1 puerto OK.
    ResumenServidor(
        nombre="QLYMSPROD01", planta="ZACATECAS",
        cpu=MetricaServidor(52.3, "verde"), gpu=MetricaServidor(61.0, "verde"),
        discos=[MontajeDisco("/", 42.0, "verde"), MontajeDisco("/home", 55.0, "verde")],
        camaras_totales=12, camaras_ok=12, camaras_no_concluyentes=0, fallas=[],
        vision_stream=[(8045, "ok")],
    ),
    # Servidor con fallas mixtas + disco en ambar y temperatura en rojo. Incluye los 2 tipos nuevos
    # del 28/10/2026 (config y resolución) y una cámara con 2 fallas a la vez (ejes independientes).
    # Vision-Stream con varios puertos (como Api_Manzanillo real), uno caído.
    ResumenServidor(
        nombre="QLYMSPROD03", planta="APAN",
        cpu=MetricaServidor(88.4, "rojo"), gpu=MetricaServidor(69.2, "verde"),
        discos=[MontajeDisco("/", 76.0, "amarillo"), MontajeDisco("/data", 91.0, "rojo")],
        camaras_totales=18, camaras_ok=7, camaras_no_concluyentes=2,
        # Orden: igual al que arma _clasificar_falla()/_resumen_servidor() en datos_reporte.py --
        # aquí a mano porque el mock no pasa por esa función (ROADMAP.md, 28/10/2026).
        fallas=[
            CamaraFalla("B07", "rojo", "Cámara sin respuesta", "Puerto 80 Timed out"),
            CamaraFalla("BX2", "ambar", "Imagen IA no disponible", "Imagen IA Timed out"),
            CamaraFalla("BX3", "ambar", "Imagen de cámara no disponible", "Imagen cámara URL error"),
            CamaraFalla(
                "AD1l1", "rojo", "Cámara movida (confirmado)", "Confirmado por un humano: la cámara se movió",
                ruta_base=_RUTA_BASE_EJEMPLO, ruta_actual=_RUTA_ACTUAL_EJEMPLO,
            ),
            # Caso de 2 fallas a la vez (imagen y configuración son ejes independientes).
            CamaraFalla(
                "DUAL1", "rojo", "Cámara movida (confirmado)", "Confirmado por un humano: la cámara se movió",
                ruta_base=_RUTA_BASE_EJEMPLO, ruta_actual=_RUTA_ACTUAL_EJEMPLO,
            ),
            CamaraFalla("SP-TE01", "morado", "Pendiente de revisión", "Desplazamiento por encima del umbral"),
            CamaraFalla("ENT1-Op01", "base_desactualizada", "Base de imágenes desactualizada", "Pendiente de que alguien suba una imagen limpia (ventana_bases.py)"),
            CamaraFalla(
                "DUAL1", "rojo", "Cambió la configuración", "",
                config_diferencias=[
                    {"categoria": "video", "campo": "StreamingChannel.Video.maxFrameRate", "base": "2000", "actual": "400"},
                ],
            ),
            CamaraFalla(
                "NF3", "rojo", "Cambió la configuración", "",
                config_diferencias=[
                    {"categoria": "compresion", "campo": "StreamingChannel.Video.constantBitRate", "base": "5120", "actual": "10240"},
                    {"categoria": "compresion", "campo": "StreamingChannel.Video.vbrUpperCap", "base": "5120", "actual": "10240"},
                    {"categoria": "network", "campo": "NetworkInterface.Link.MACAddress", "base": "4c:f5:dc:90:62:f2", "actual": "4c:f5:dc:90:63:3a"},
                ],
            ),
            CamaraFalla("AD1r1", "rojo", "Cambio de resolución", "Base: 1920 x 1080 | Hoy: 1280 x 720"),
        ],
        vision_stream=[(12046, "ok"), (12047, "caido"), (13045, "ok"), (13048, "ok")],
    ),
    # Servidor sin datos de monitoreo todavia (no esta en Monit_Servers_V2). Vision-Stream nunca
    # visto (caso excepcional) -- "Puerto Desconocido".
    ResumenServidor(
        nombre="QLYMSPROD05", planta="TOCANCIPA",
        cpu=None, gpu=None, discos=[],
        camaras_totales=9, camaras_ok=8, camaras_no_concluyentes=0,
        fallas=[CamaraFalla("EVP", "rojo", "Cámara sin respuesta", "Puerto 80 Service Unavailable")],
        vision_stream=[],
    ),
    # Todas sus cámaras bien (sin fallas), pero su Vision-Stream está caído -- genera su propia hoja
    # de detalle igual, solo con la tabla de Vision-Stream (ROADMAP.md, 28/10/2026).
    ResumenServidor(
        nombre="QLYMSPROD02", planta="ZACATECAS",
        cpu=MetricaServidor(58.1, "verde"), gpu=MetricaServidor(64.5, "verde"),
        discos=[MontajeDisco("/", 48.0, "verde")],
        camaras_totales=44, camaras_ok=44, camaras_no_concluyentes=0, fallas=[],
        vision_stream=[(8045, "caido")],
    ),
]


def main() -> None:
    ruta_salida = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("mock_reporte_ejecutivo.pdf")
    construir_pdf("AbInBev", date(2026, 10, 21), SERVIDORES, ruta_salida)
    print(f"OK -- generado en {ruta_salida.resolve()}")


if __name__ == "__main__":
    main()
