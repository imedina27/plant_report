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

from comparacion.image_compare import CHECK_PLANTS_ROOT
from comparacion.image_compare import base_path as ruta_base_imagen
from integraciones import monit_client
from reporte.reporte_ejecutivo import CamaraFalla, ResumenServidor, construir_pdf

load_dotenv()

REPORTES_ROOT = Path(os.environ["REPORTES_ROOT"])


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
    """Reglas acordadas (ROADMAP.md, Fase 4): 🔴 rojo, 🟣 morado y 🔵 base desactualizada siempre
    cuentan, igual que una cámara sin respuesta ese día (el `.log` del servidor, no la comparación,
    ver sección 3). 🟡 ámbar nunca llega aquí -- desde el 3er día seguido se convierte en morado
    automáticamente (`db._siguiente_estado`), así que un ámbar visto en esta función siempre es de
    1 o 2 días (ver `_resumen_servidor`, columna "No concluyente").

    "Estado" muestra una etiqueta descriptiva (no el color crudo) y "Motivo" el detalle técnico
    puro, por separado (pedido 21/10/2026) -- antes venían concatenados en un solo texto. Las
    cámaras sin respuesta no traen imágenes (no hay "actual" que capturar ese día); las demás sí,
    incluida base desactualizada (ayuda a ver de un vistazo si de verdad hace falta reemplazarla).
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
    if fila["estado_actual"] == "base_desactualizada":
        # Antes no contaba como falla (era un estado "en proceso", ya marcado por un humano) --
        # pedido 22/10/2026: ahora sí, para que la suma de las columnas del resumen cierre siempre
        # contra "Cámaras totales" y no quede ninguna cámara invisible en el reporte.
        ruta_base, ruta_actual = _rutas_imagenes(cliente, planta, servidor, fila["camara"], fecha)
        return CamaraFalla(
            fila["camara"], "base_desactualizada", "Base de imágenes desactualizada",
            fila["imagen_motivo"] or "Pendiente de que alguien suba una imagen limpia (ventana_bases.py)",
            ruta_base, ruta_actual,
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


def _resolver_cliente(conn, cliente: str, fecha: date) -> str | None:
    """Encuentra el nombre del cliente tal cual está guardado en la base (mayúsculas/minúsculas
    exactas), sin importar cómo lo haya escrito quien pasó `--client` -- `None` si ese cliente no
    tiene ningún dato para esa fecha (pedido 22/10/2026: `--client ABINBEV` generaba un PDF vacío en
    vez de encontrar `AbInBev`, porque Postgres compara texto distinguiendo mayúsculas)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT p.cliente
            FROM historial_comparacion h JOIN perfil_camara p ON p.id = h.camara_id
            WHERE h.fecha = %s AND LOWER(p.cliente) = LOWER(%s)
            """,
            (fecha, cliente),
        )
        fila = cur.fetchone()
        return fila[0] if fila else None


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
    # Ámbar de 1 o 2 días -- nunca llega al 3ro sin convertirse en morado (ver _siguiente_estado),
    # así que no hace falta revisar "dias_no_concluyente_consecutivos" aquí (pedido 22/10/2026: antes
    # estas cámaras no aparecían en ninguna columna del resumen, ni como OK ni como falla).
    camaras_no_concluyentes = sum(
        1 for fila in filas if fila["estado_actual"] == "amarillo" and fila["log_estado"] != "ERROR"
    )

    temperaturas = monit_client.temperaturas_promedio_dia(servidor, fecha)
    discos = monit_client.uso_disco_actual(servidor)

    return ResumenServidor(
        nombre=servidor, planta=planta,
        cpu=temperaturas["cpu"] if temperaturas else None,
        gpu=temperaturas["gpu"] if temperaturas else None,
        discos=discos,
        camaras_totales=len(filas), camaras_ok=camaras_ok,
        camaras_no_concluyentes=camaras_no_concluyentes, fallas=fallas,
    )


def generar_reportes_del_dia(conn, fecha: date, cliente: str | None = None) -> dict[str, Path]:
    """Un PDF por cliente que tuvo al menos una cámara procesada ese día. Regresa
    `{cliente: ruta}` (`REPORTES_ROOT/<cliente>/<fecha>_<cliente>.pdf`) -- el diccionario completo
    es lo que `correo.py` necesita para saber qué adjuntarle a quién.

    `cliente`, si se da, acota TODO el proceso a ese cliente -- no solo qué cámaras se compararon en
    `main.py` (`--client`), también qué se reporta y a quién se le envía correo. Sin esto, un `main.py
    --client AbInBev` corrido el mismo día que ya hay otro cliente en la base de datos (de una
    corrida anterior ese día) terminaba generando -- y enviando -- el reporte de ese otro cliente
    también, porque esta función consultaba "qué clientes tienen datos hoy" sin filtrar (bug real,
    detectado 21/10/2026: reenvió un correo de Api_Manzanillo sin haberlo pedido).

    Si `cliente` no coincide con ningún dato de esa fecha (typo, mayúsculas distintas, o un cliente
    que de plano no se procesó ese día), regresa `{}` en vez de generar un PDF vacío (bug real,
    detectado 22/10/2026 con `--client ABINBEV`)."""
    rutas: dict[str, Path] = {}
    if cliente is not None:
        cliente_real = _resolver_cliente(conn, cliente, fecha)
        if cliente_real is None:
            return rutas
        clientes = [cliente_real]
    else:
        clientes = _clientes_del_dia(conn, fecha)
    for cliente in clientes:
        servidores = [
            _resumen_servidor(conn, cliente, planta, servidor, fecha)
            for planta, servidor in _servidores_del_cliente(conn, cliente, fecha)
        ]
        carpeta_cliente = REPORTES_ROOT / cliente
        carpeta_cliente.mkdir(parents=True, exist_ok=True)
        ruta = carpeta_cliente / f"{fecha:%d%m%Y}_{cliente}.pdf"
        construir_pdf(cliente, fecha, servidores, ruta)
        rutas[cliente] = ruta
    return rutas
