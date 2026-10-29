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

import re

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


_RE_CODIGO_ERROR = re.compile(r"\s*\[\d+\]\s*$")


def _sin_codigo_error(texto: str) -> str:
    """Quita el código de error final del texto crudo del log (ej. `" [111]"`) -- no es información
    relevante para el cliente que lee el PDF (pedido 28/10/2026). El dato completo se queda igual en
    `historial_comparacion.log_motivo`/`imagen_motivo`, esto solo afecta cómo se ve en el reporte."""
    return _RE_CODIGO_ERROR.sub("", texto).strip()


def _etiqueta_sin_respuesta(log_motivo: str | None) -> tuple[str, str, int]:
    """`(etiqueta, color, orden)` según qué paso falló en el `.log` del servidor (ver
    `log_parse.py`) -- no todos los fallos son igual de graves (pedido 21/10/2026, tras ver `AD1p`
    con "Configuración Unknow error [790]" y `AD1r2` con "Puerto 80 Timed out [111]" mostrando el
    mismo letrero genérico, aunque uno sigue funcionando bien y el otro está totalmente caído):

    - "Puerto 80 ..." -- no contestó en absoluto, ningún otro paso se intentó siquiera. El más grave.
    - "Imagen IA ..." / "Imagen cámara ..." -- el puerto sí respondió, falló solo al traer la imagen
      -- ámbar, no rojo (pedido 28/10/2026: no es un fallo catastrófico, la cámara sigue viva).
    - "Configuración ..." -- puerto e imagen bien, solo falló al traer la configuración -- ámbar.
    - Cualquier otro texto no previsto -- "Error desconocido", último recurso de este grupo (en rojo,
      más vale no subestimarlo).

    `orden` fija la posición en la tabla "Cámaras con Falla" (ROADMAP.md, 28/10/2026, orden
    acordado con el usuario) -- ver `_ORDEN_*` abajo para el resto de categorías.
    """
    texto = log_motivo or ""
    if texto.startswith("Puerto 80"):
        return "Cámara sin respuesta", "rojo", 1
    if texto.startswith("Imagen IA"):
        return "Imagen IA no disponible", "ambar", 2
    if texto.startswith("Imagen cámara"):
        return "Imagen de cámara no disponible", "ambar", 3
    if texto.startswith("Configuración"):
        return "Configuración no disponible", "ambar", 4
    return "Error desconocido", "rojo", 5


# Orden de aparición en "Cámaras con Falla" (ROADMAP.md, 28/10/2026) -- 1-5 vienen de
# _etiqueta_sin_respuesta() arriba; el resto se usa directo en _clasificar_falla().
_ORDEN_CAMARA_MOVIDA = 6
_ORDEN_PENDIENTE_REVISION = 7
_ORDEN_BASE_DESACTUALIZADA = 8
_ORDEN_BASE_DESACTUALIZADA_URGENTE = 9
_ORDEN_CONFIG_CAMBIO = 10
_ORDEN_RESOLUCION_DISTINTA = 11

DIAS_BASE_DESACTUALIZADA_URGENTE = 3  # ver _clasificar_falla


def _clasificar_falla(
    fila: dict, cliente: str, planta: str, servidor: str, fecha: date,
) -> list[tuple[int, CamaraFalla]]:
    """Reglas acordadas (ROADMAP.md, Fase 4, ampliadas 28/10/2026): 🔴 rojo, 🟣 morado y 🔵 base
    desactualizada siempre cuentan, igual que una cámara sin respuesta ese día (el `.log` del
    servidor, no la comparación, ver sección 3). 🟡 ámbar "normal" nunca llega aquí -- desde el 3er
    día seguido se convierte en morado automáticamente (`db._siguiente_estado`), así que un ámbar
    visto en esta función siempre es de 1 o 2 días (ver `_resumen_servidor`, columna "No
    concluyente") o de uno de los casos "no catastróficos" de `_etiqueta_sin_respuesta`.

    Regresa una **lista** de `(orden, CamaraFalla)`, no una sola -- a diferencia de antes, imagen y
    configuración son ejes independientes (ROADMAP.md, 28/10/2026): una misma cámara puede tener un
    problema de imagen *y* uno de configuración el mismo día, y ambos deben verse, no solo el
    primero que se encuentre. Si no respondió nada ese día (`log_estado == 'ERROR'`), no hay nada
    más que comparar -- se regresa de inmediato sin revisar los demás ejes.

    "Estado" muestra una etiqueta descriptiva (no el color crudo) y "Motivo" el detalle técnico, sin
    el código de error final (pedido 28/10/2026, ver `_sin_codigo_error`). Las cámaras sin respuesta
    no traen imágenes (no hay "actual" que capturar ese día); las demás sí, incluida base
    desactualizada (ayuda a ver de un vistazo si de verdad hace falta reemplazarla).
    """
    if fila["log_estado"] == "ERROR":
        etiqueta, color, orden = _etiqueta_sin_respuesta(fila["log_motivo"])
        motivo = _sin_codigo_error(fila["log_motivo"] or "")
        return [(orden, CamaraFalla(fila["camara"], color, etiqueta, motivo))]

    resultados: list[tuple[int, CamaraFalla]] = []
    ruta_base, ruta_actual = _rutas_imagenes(cliente, planta, servidor, fila["camara"], fecha)

    if fila["estado_actual"] == "rojo":
        motivo = _sin_codigo_error(fila["imagen_motivo"] or "Confirmado por un humano")
        resultados.append((_ORDEN_CAMARA_MOVIDA, CamaraFalla(
            fila["camara"], "rojo", "Cámara movida (confirmado)", motivo, ruta_base, ruta_actual,
        )))
    elif fila["estado_actual"] == "morado":
        motivo = _sin_codigo_error(fila["imagen_motivo"] or "Desplazamiento por encima del umbral")
        resultados.append((_ORDEN_PENDIENTE_REVISION, CamaraFalla(
            fila["camara"], "morado", "Pendiente de revisión", motivo, ruta_base, ruta_actual,
        )))
    elif fila["estado_actual"] == "base_desactualizada":
        # Antes no contaba como falla (era un estado "en proceso", ya marcado por un humano) --
        # pedido 22/10/2026: ahora sí, para que la suma de las columnas del resumen cierre siempre
        # contra "Cámaras totales" y no quede ninguna cámara invisible en el reporte.
        motivo = _sin_codigo_error(
            fila["imagen_motivo"] or "Pendiente de que alguien suba una imagen limpia (ventana_bases.py)"
        )
        dias_sin_resolver = (fecha - fila["estado_desde"]).days if fila["estado_desde"] else 0
        if dias_sin_resolver >= DIAS_BASE_DESACTUALIZADA_URGENTE:
            # Pedido 26/10/2026: congelada sí, pero no indefinidamente sin presión -- a los 3 días
            # sin resolver se ve con la misma urgencia que un "Mal" confirmado, para obligar a
            # reemplazarla pronto. No cambia `estado_actual` en la base de datos (sigue
            # "base_desactualizada" -- la cámara sigue en la lista de `ui/ventana_bases.py` y
            # `main.py` sigue sin comparar nada contra esa base); es solo cómo se ve en el reporte.
            resultados.append((_ORDEN_BASE_DESACTUALIZADA_URGENTE, CamaraFalla(
                fila["camara"], "rojo",
                f"Base de imágenes desactualizada ({dias_sin_resolver} días sin resolver)",
                motivo, ruta_base, ruta_actual,
            )))
        else:
            resultados.append((_ORDEN_BASE_DESACTUALIZADA, CamaraFalla(
                fila["camara"], "base_desactualizada", "Base de imágenes desactualizada",
                motivo, ruta_base, ruta_actual,
            )))

    # Eje de resolución (ROADMAP.md, 28/10/2026) -- independiente de estado_actual, que NO cambia
    # cuando esto pasa (ver db._siguiente_estado): un problema real distinto a "la cámara se movió".
    # Caso real que lo originó: una base reemplazada por error con una foto de otra resolución, sin
    # que el .json base se enterara (son comparaciones independientes).
    if fila["imagen_status"] == "RESOLUCION DISTINTA":
        resultados.append((_ORDEN_RESOLUCION_DISTINTA, CamaraFalla(
            fila["camara"], "rojo", "Cambio de resolución", fila["imagen_motivo"] or "",
        )))

    # Eje de configuración (ROADMAP.md, 28/10/2026) -- independiente también. `config_estado_actual`
    # es el estado vivo de `perfil_camara` (igual patrón que estado_actual/rojo): se queda en
    # "incidencia" sin volver a preguntar hasta que se resuelva (ver pedir_revision_config()).
    if fila["config_estado_actual"] == "incidencia":
        resultados.append((_ORDEN_CONFIG_CAMBIO, CamaraFalla(
            fila["camara"], "rojo", "Cambió la configuración", "",
            config_diferencias=fila["config_diferencias"] or [],
        )))

    return resultados


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


def _vision_stream_servidor(conn, cliente: str, planta: str, servidor: str, fecha: date) -> list[tuple[int, str]]:
    """`[(puerto, estado)]` de ese servidor ese día (ROADMAP.md, 28/10/2026) -- un servidor puede
    tener más de un puerto de IA (ej. Api_Manzanillo, con hasta 4). Lista vacía si ese día no hay
    fila (servidor nunca visto, o el `.log` de hoy no trajo ningún bloque de YAML)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT si.puerto, hsi.estado
            FROM historial_servicio_ia hsi JOIN servicio_ia si ON si.id = hsi.servicio_id
            WHERE si.cliente = %s AND si.planta = %s AND si.servidor = %s AND hsi.fecha = %s
            ORDER BY si.puerto
            """,
            (cliente, planta, servidor, fecha),
        )
        return cur.fetchall()


def _resumen_servidor(conn, cliente: str, planta: str, servidor: str, fecha: date) -> ResumenServidor:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.camara, p.estado_actual, p.dias_no_concluyente_consecutivos, p.estado_desde,
                   p.config_estado_actual,
                   h.imagen_status, h.imagen_motivo, h.config_diferencias, h.log_estado, h.log_motivo
            FROM historial_comparacion h JOIN perfil_camara p ON p.id = h.camara_id
            WHERE p.cliente = %s AND p.planta = %s AND p.servidor = %s AND h.fecha = %s
            ORDER BY p.camara
            """,
            (cliente, planta, servidor, fecha),
        )
        columnas = [d.name for d in cur.description]
        filas = [dict(zip(columnas, f)) for f in cur.fetchall()]

    # Cada cámara puede aportar 0, 1 o 2 fallas (imagen y configuración son ejes independientes,
    # ROADMAP.md 28/10/2026) -- se aplanan todas y se ordenan por la prioridad acordada con el
    # usuario, cámara como criterio de desempate.
    fallas_con_orden = [
        item
        for fila in filas
        for item in _clasificar_falla(fila, cliente, planta, servidor, fecha)
    ]
    fallas = [cf for _orden, cf in sorted(fallas_con_orden, key=lambda t: (t[0], t[1].camara))]

    # Una cámara con cualquier falla (imagen o configuración) no cuenta como "OK" ni como "no
    # concluyente", aunque su semáforo de imagen esté en verde/ámbar -- si no, el conteo del resumen
    # dejaría de cerrar contra "Cámaras totales" ahora que una cámara puede tener 2 fallas a la vez.
    camaras_con_falla = {cf.camara for _orden, cf in fallas_con_orden}
    camaras_ok = sum(
        1 for fila in filas
        if fila["estado_actual"] == "verde" and fila["log_estado"] != "ERROR"
        and fila["camara"] not in camaras_con_falla
    )
    # Ámbar de 1 o 2 días -- nunca llega al 3ro sin convertirse en morado (ver _siguiente_estado),
    # así que no hace falta revisar "dias_no_concluyente_consecutivos" aquí (pedido 22/10/2026: antes
    # estas cámaras no aparecían en ninguna columna del resumen, ni como OK ni como falla).
    camaras_no_concluyentes = sum(
        1 for fila in filas
        if fila["estado_actual"] == "amarillo" and fila["log_estado"] != "ERROR"
        and fila["camara"] not in camaras_con_falla
    )

    temperaturas = monit_client.temperaturas_promedio_dia(servidor, fecha)
    discos = monit_client.uso_disco_actual(servidor)
    vision_stream = _vision_stream_servidor(conn, cliente, planta, servidor, fecha)

    return ResumenServidor(
        nombre=servidor, planta=planta,
        cpu=temperaturas["cpu"] if temperaturas else None,
        gpu=temperaturas["gpu"] if temperaturas else None,
        discos=discos,
        camaras_totales=len(filas), camaras_ok=camaras_ok,
        camaras_no_concluyentes=camaras_no_concluyentes, fallas=fallas,
        vision_stream=vision_stream,
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
