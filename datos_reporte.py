"""Arma los datos del reporte ejecutivo (Fase 4, ROADMAP.md) a partir de lo que ya quedó en la
base de datos (perfil_camara/historial_comparacion) más lo que reporta Monit_Servers_V2 (CPU/GPU/
disco, vía monit_client.py). Separado de `reporte_ejecutivo.py` (que solo sabe construir el PDF, sin
tocar ninguna base de datos) y de `main.py` (que solo orquesta la corrida diaria).
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

import monit_client
from image_compare import CHECK_PLANTS_ROOT
from image_compare import base_path as ruta_base_imagen
from reporte_ejecutivo import CamaraFalla, ResumenServidor, construir_pdf

load_dotenv()

REPORTES_ROOT = Path(os.environ["REPORTES_ROOT"])

# Ámbar (NO CONCLUYENTE) solo cuenta como falla a partir del 3er día seguido (decidido en el
# ROADMAP, sección 4) -- un día aislado puede ser lluvia en el lente, no amerita avisar a Gerencia.
_DIAS_AMBAR_PARA_FALLA = 3


def _rutas_imagenes(
    cliente: str, planta: str, servidor: str, camara: str, fecha: date,
) -> tuple[Path | None, Path | None]:
    """`(ruta_base, ruta_actual)` para mostrar en el PDF (pedido 21/10/2026) -- `None` en
    cualquiera de las dos si el archivo no existe (no detiene el reporte, solo omite las imágenes
    de esa cámara)."""
    base = ruta_base_imagen(cliente, planta, servidor, camara)
    patron = f"{cliente}/*/{fecha:%d%m%y}/{planta}/{servidor}/{camara}.jpg"
    actual = next(CHECK_PLANTS_ROOT.glob(patron), None)
    return (base if base.exists() else None), actual


def _etiqueta_sin_respuesta(log_motivo: str | None) -> tuple[str, str]:
    """`(etiqueta, color)` según qué paso falló en el `.log` del servidor (ver `log_parse.py`) --
    no todos los fallos son igual de graves (pedido 21/10/2026, tras ver `AD1p` con "Configuración
    Unknow error [790]" y `AD1r2` con "Puerto 80 Timed out [111]" mostrando el mismo letrero
    genérico, aunque uno sigue funcionando bien y el otro está totalmente caído):

    - "Puerto 80 ..." -- no contestó en absoluto, ningún otro paso se intentó siquiera. El más grave.
    - "Imagen IA ..." / "Imagen cámara ..." -- el puerto sí respondió, falló solo al traer la imagen.
    - "Configuración ..." -- puerto e imagen bien, solo falló al traer la configuración -- la cámara
      en sí está viva y capturando; se deja en ámbar, no rojo, porque es el menos grave de los tres.
    - Cualquier otro texto no previsto -- "Error desconocido", en rojo (más vale no subestimarlo).
    """
    texto = log_motivo or ""
    if texto.startswith("Puerto 80"):
        return "Cámara sin respuesta", "rojo"
    if texto.startswith("Imagen IA") or texto.startswith("Imagen cámara"):
        return "Imagen no disponible", "rojo"
    if texto.startswith("Configuración"):
        return "Configuración no disponible", "amarillo"
    return "Error desconocido", "rojo"


def _clasificar_falla(fila: dict, cliente: str, planta: str, servidor: str, fecha: date) -> CamaraFalla | None:
    """Reglas acordadas (ROADMAP.md, Fase 4): 🔴 rojo y 🟣 morado siempre cuentan, igual que una
    cámara sin respuesta ese día (el `.log` del servidor, no la comparación, ver sección 3). 🟡
    ámbar solo cuenta desde el 3er día seguido. 🔵 base desactualizada NO cuenta -- ya es un estado
    "en proceso", alguien ya lo marcó.

    "Estado" muestra una etiqueta descriptiva (no el color crudo) y "Motivo" el detalle técnico
    puro, por separado (pedido 21/10/2026) -- antes venían concatenados en un solo texto. Las
    cámaras sin respuesta no traen imágenes (no hay "actual" que capturar ese día); las demás sí,
    incluido ámbar (ayuda a ver si es lente sucio/obstrucción).
    """
    if fila["log_estado"] == "ERROR":
        etiqueta, color = _etiqueta_sin_respuesta(fila["log_motivo"])
        return CamaraFalla(fila["camara"], color, etiqueta, fila["log_motivo"] or "")

    if fila["estado_actual"] == "rojo":
        ruta_base, ruta_actual = _rutas_imagenes(cliente, planta, servidor, fila["camara"], fecha)
        return CamaraFalla(
            fila["camara"], "rojo", "Cámara movida (confirmado)",
            fila["imagen_motivo"] or "Confirmado por un humano", ruta_base, ruta_actual,
        )
    if fila["estado_actual"] == "morado":
        ruta_base, ruta_actual = _rutas_imagenes(cliente, planta, servidor, fila["camara"], fecha)
        return CamaraFalla(
            fila["camara"], "morado", "Pendiente de revisión",
            fila["imagen_motivo"] or "Desplazamiento por encima del umbral", ruta_base, ruta_actual,
        )
    if (
        fila["estado_actual"] == "amarillo"
        and fila["dias_no_concluyente_consecutivos"] >= _DIAS_AMBAR_PARA_FALLA
    ):
        dias = fila["dias_no_concluyente_consecutivos"]
        ruta_base, ruta_actual = _rutas_imagenes(cliente, planta, servidor, fila["camara"], fecha)
        return CamaraFalla(
            fila["camara"], "amarillo", f"No concluyente ({dias} días seguidos)",
            fila["imagen_motivo"] or "Ningún método alcanza suficiente confianza", ruta_base, ruta_actual,
        )
    return None


def _clientes_del_dia(conn, fecha: date) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT p.cliente
            FROM historial_comparacion h JOIN perfil_camara p ON p.id = h.camara_id
            WHERE h.fecha = %s
            ORDER BY 1
            """,
            (fecha,),
        )
        return [fila[0] for fila in cur.fetchall()]


def _servidores_del_cliente(conn, cliente: str, fecha: date) -> list[tuple[str, str]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT p.planta, p.servidor
            FROM historial_comparacion h JOIN perfil_camara p ON p.id = h.camara_id
            WHERE p.cliente = %s AND h.fecha = %s
            ORDER BY 1, 2
            """,
            (cliente, fecha),
        )
        return cur.fetchall()


def _resumen_servidor(conn, cliente: str, planta: str, servidor: str, fecha: date) -> ResumenServidor:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.camara, p.estado_actual, p.dias_no_concluyente_consecutivos,
                   h.imagen_motivo, h.log_estado, h.log_motivo
            FROM historial_comparacion h JOIN perfil_camara p ON p.id = h.camara_id
            WHERE p.cliente = %s AND p.planta = %s AND p.servidor = %s AND h.fecha = %s
            ORDER BY p.camara
            """,
            (cliente, planta, servidor, fecha),
        )
        columnas = [d.name for d in cur.description]
        filas = [dict(zip(columnas, f)) for f in cur.fetchall()]

    fallas = [
        f for f in (_clasificar_falla(fila, cliente, planta, servidor, fecha) for fila in filas)
        if f is not None
    ]
    camaras_ok = sum(
        1 for fila in filas if fila["estado_actual"] == "verde" and fila["log_estado"] != "ERROR"
    )

    temperaturas = monit_client.temperaturas_promedio_dia(servidor, fecha)
    discos = monit_client.uso_disco_actual(servidor)

    return ResumenServidor(
        nombre=servidor, planta=planta,
        cpu=temperaturas["cpu"] if temperaturas else None,
        gpu=temperaturas["gpu"] if temperaturas else None,
        discos=discos,
        camaras_totales=len(filas), camaras_ok=camaras_ok, fallas=fallas,
    )


def generar_reportes_del_dia(conn, fecha: date) -> dict[str, Path]:
    """Un PDF por cliente que tuvo al menos una cámara procesada ese día. Regresa
    `{cliente: ruta}` (`REPORTES_ROOT/<cliente>/<fecha>_<cliente>.pdf`) -- el diccionario completo
    es lo que `correo.py` necesita para saber qué adjuntarle a quién."""
    rutas: dict[str, Path] = {}
    for cliente in _clientes_del_dia(conn, fecha):
        servidores = [
            _resumen_servidor(conn, cliente, planta, servidor, fecha)
            for planta, servidor in _servidores_del_cliente(conn, cliente, fecha)
        ]
        carpeta_cliente = REPORTES_ROOT / cliente
        carpeta_cliente.mkdir(parents=True, exist_ok=True)
        ruta = carpeta_cliente / f"{fecha:%Y%m%d}_{cliente}.pdf"
        construir_pdf(cliente, fecha, servidores, ruta)
        rutas[cliente] = ruta
    return rutas
