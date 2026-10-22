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
from reporte_ejecutivo import CamaraFalla, ResumenServidor, construir_pdf

load_dotenv()

REPORTES_ROOT = Path(os.environ["REPORTES_ROOT"])

# Ámbar (NO CONCLUYENTE) solo cuenta como falla a partir del 3er día seguido (decidido en el
# ROADMAP, sección 4) -- un día aislado puede ser lluvia en el lente, no amerita avisar a Gerencia.
_DIAS_AMBAR_PARA_FALLA = 3


def _clasificar_falla(fila: dict) -> CamaraFalla | None:
    """Reglas acordadas (ROADMAP.md, Fase 4): 🔴 rojo y 🟣 morado siempre cuentan, igual que una
    cámara sin respuesta ese día (el `.log` del servidor, no la comparación, ver sección 3). 🟡
    ámbar solo cuenta desde el 3er día seguido. 🔵 base desactualizada NO cuenta -- ya es un estado
    "en proceso", alguien ya lo marcó."""
    if fila["log_estado"] == "ERROR":
        return CamaraFalla(fila["camara"], "rojo", f"Servidor sin respuesta -- {fila['log_motivo']}")
    if fila["estado_actual"] == "rojo":
        return CamaraFalla(
            fila["camara"], "rojo", fila["imagen_motivo"] or "Confirmado: la cámara se movió",
        )
    if fila["estado_actual"] == "morado":
        return CamaraFalla(
            fila["camara"], "morado",
            fila["imagen_motivo"] or "Desplazamiento por encima del umbral -- pendiente de revisión",
        )
    if (
        fila["estado_actual"] == "amarillo"
        and fila["dias_no_concluyente_consecutivos"] >= _DIAS_AMBAR_PARA_FALLA
    ):
        return CamaraFalla(
            fila["camara"], "amarillo",
            f"NO CONCLUYENTE {fila['dias_no_concluyente_consecutivos']} días seguidos",
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

    fallas = [f for f in (_clasificar_falla(fila) for fila in filas) if f is not None]
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
