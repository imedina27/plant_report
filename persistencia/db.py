"""Persistencia en PostgreSQL (Fase 3, ROADMAP.md sección "Persistencia en base de datos").

`perfil_camara` es el catálogo de cámaras y, a la vez, su estado vivo (semáforo, sección 2.7) y su
perfil estadístico. `historial_comparacion` es el registro crudo, una fila por cámara por día.
"""

from __future__ import annotations

import datetime
import os
import statistics

import psycopg2
import psycopg2.extensions
from dotenv import load_dotenv
from psycopg2.extras import Json

load_dotenv()


def get_connection() -> psycopg2.extensions.connection:
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=os.environ["DB_PORT"],
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
    )


def obtener_camara(conn: psycopg2.extensions.connection, cliente: str, planta: str,
                    servidor: str, camara: str) -> dict:
    """Trae el perfil de la cámara, creándolo con sus valores por defecto si es la primera vez."""
    with conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO perfil_camara (cliente, planta, servidor, camara)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (cliente, planta, servidor, camara) DO NOTHING
            """,
            (cliente, planta, servidor, camara),
        )
        cur.execute(
            """
            SELECT id, estado_actual, dias_no_concluyente_consecutivos, base_reemplazada_el,
                   dias_borroso_consecutivos, p95_desplazamiento,
                   config_estado_actual, config_incidencia_desde
            FROM perfil_camara
            WHERE cliente = %s AND planta = %s AND servidor = %s AND camara = %s
            """,
            (cliente, planta, servidor, camara),
        )
        (id_, estado_actual, dias, base_reemplazada_el, dias_borroso, p95_desp,
         config_estado_actual, config_incidencia_desde) = cur.fetchone()
        return {
            "id": id_, "estado_actual": estado_actual, "dias_no_concluyente_consecutivos": dias,
            "base_reemplazada_el": base_reemplazada_el, "dias_borroso_consecutivos": dias_borroso,
            "p95_desplazamiento": p95_desp,
            "config_estado_actual": config_estado_actual,
            "config_incidencia_desde": config_incidencia_desde,
        }


DIAS_AMARILLO_PARA_REVISION = 3  # ver _siguiente_estado
DIAS_BORROSO_PARA_REVISION = 3  # ver _siguiente_estado -- mismo criterio, pero para nitidez


def _siguiente_estado(
    estado_actual: str, imagen_status: str | None, veredicto_humano: str | None,
    dias_no_concl_previo: int = 0, fuerza_revision_borrosa: bool = False,
    fuerza_revision_salud: bool = False,
) -> str:
    """Máquina de estados del semáforo (ROADMAP.md, sección 2.7).

    Un ámbar (`NO CONCLUYENTE`) que lleva `DIAS_AMARILLO_PARA_REVISION` días seguidos pasa a morado
    -- deja de ser "ninguno de los dos métodos está seguro" para convertirse en "alguien tiene que
    decidir", igual que un `REVISAR` normal (pedido 22/10/2026: antes se quedaba en ámbar para
    siempre si nunca llegaba a confirmarse como movimiento real, sin que ningún humano lo viera).

    `fuerza_revision_borrosa` (26/10/2026, detección de lente sucio/desenfocado): mismo patrón --
    aunque la geometría diga `OK`, una nitidez sospechosa sostenida `DIAS_BORROSO_PARA_REVISION`
    días seguidos también manda a morado, para que un humano lo vea.

    `fuerza_revision_salud` (26/10/2026, salud absoluta de imagen): mismo efecto, pero como
    disparador inmediato de un solo día -- una obstrucción total no necesita esperar varios días
    para confirmarse, a diferencia de un desenfoque gradual."""
    if veredicto_humano in ("bien", "actualizar_base", "obstruida"):
        # "actualizar_base" (26/10/2026): la base estaba vieja, pero la foto de hoy ya sirve y se
        # usó de inmediato como base nueva (ver main.py) -- el problema ya quedó resuelto.
        # "obstruida" (28/10/2026): no es que la cámara se haya movido -- algo temporal tapó la
        # escena (camión, objeto de paso). La cámara sigue bien, solo la foto de hoy no cuenta
        # para el historial que alimenta la mediana (ver main.py).
        return "verde"
    if veredicto_humano == "mal":
        return "rojo"
    if veredicto_humano == "desactualizada":
        return "base_desactualizada"

    if estado_actual in ("rojo", "base_desactualizada"):
        # Incidencia abierta: no se reabre la ventana de revisión (sección 2.7/2.8), solo se
        # recupera sola si la comparación automática vuelve a dar OK.
        return "verde" if imagen_status == "OK" else estado_actual

    if imagen_status in ("OK", "BASE CREADA"):
        return "morado" if (fuerza_revision_borrosa or fuerza_revision_salud) else "verde"
    if imagen_status == "REVISAR":
        return "morado"
    if imagen_status == "NO CONCLUYENTE":
        return "morado" if dias_no_concl_previo + 1 >= DIAS_AMARILLO_PARA_REVISION else "amarillo"
    return estado_actual


def _siguiente_estado_config(
    estado_actual: str, config_status: str | None, veredicto_humano: str | None,
) -> str:
    """Semáforo de configuración (ROADMAP.md, 28/10/2026) -- más simple que `_siguiente_estado()`:
    solo "ok"/"incidencia", porque a diferencia de ORB/fase (señales ruidosas), un cambio de
    configuración es una comparación exacta campo por campo -- no hay ambigüedad que amerite
    estados intermedios como ámbar/morado.

    "incidencia" se queda así (sin volver a preguntar, ver main.py) hasta que alguien presione
    "Aceptar Cambio" (confirma que el cambio es legítimo, reemplaza la base), o la configuración
    real de la cámara vuelva a coincidir con la base por su cuenta (alguien la corrigió a mano,
    sin pasar por esta ventana)."""
    if veredicto_humano == "aceptar_cambio":
        return "ok"
    if veredicto_humano == "mal":
        return "incidencia"
    if estado_actual == "incidencia":
        return "ok" if config_status == "OK" else "incidencia"
    return estado_actual


def guardar_resultado(
    conn: psycopg2.extensions.connection, camara_id: int, fecha: datetime.date,
    estado_actual_previo: str, dias_no_concl_previo: int,
    config_result: dict | None, imagen_result: dict | None,
    veredicto_humano: str | None, modo: str,
    log_info: dict | None = None, dias_borroso_previo: int = 0,
    config_estado_previo: str = "ok", config_incidencia_desde_previo: datetime.date | None = None,
    config_veredicto_humano: str | None = None,
) -> tuple[str, str]:
    """Escribe el resultado de una cámara (upsert por día) y actualiza su estado vivo.

    Se llama una vez por cámara, justo después de resolverla -- no en lote al final de la corrida
    (ver ROADMAP.md, sección 3): así un fallo de conexión a media corrida solo pierde la cámara en
    curso, no el veredicto humano ya dado en las cámaras anteriores.

    `log_info` viene de `log_parse.parsear_log_servidor()`: el diagnóstico de conexión/captura del
    `.log` del servidor para esta cámara (si el programa externo de revisión logró procesarla ese
    día, y si no, por qué) -- independiente de si Fase 1/2 encontraron algo que comparar.

    Regresa `(nuevo_estado, nuevo_config_estado)` -- el semáforo de imagen y el de configuración
    (ROADMAP.md, 28/10/2026), cada uno independiente del otro.
    """
    imagen_status = imagen_result["status"] if imagen_result else None
    nitidez_sospechosa = imagen_result.get("nitidez_sospechosa") if imagen_result else None
    salud_sospechosa = imagen_result.get("salud_sospechosa") if imagen_result else None
    fuerza_revision_borrosa = (
        nitidez_sospechosa is True and dias_borroso_previo + 1 >= DIAS_BORROSO_PARA_REVISION
    )
    fuerza_revision_salud = salud_sospechosa is True
    nuevo_estado = _siguiente_estado(
        estado_actual_previo, imagen_status, veredicto_humano, dias_no_concl_previo,
        fuerza_revision_borrosa, fuerza_revision_salud,
    )
    if imagen_status == "NO CONCLUYENTE":
        nuevo_dias = dias_no_concl_previo + 1
    elif imagen_status is None:
        # Sin imagen que comparar ese día (ej. falla de conexión, ver log_parse.py) -- no hubo
        # comparación real, así que la racha ni suma ni se reinicia (pedido 22/10/2026: antes se
        # reiniciaba a 0, perdiendo días ya acumulados por pura mala suerte de conexión y retrasando
        # sin motivo real que se forzara la revisión al 3er día).
        nuevo_dias = dias_no_concl_previo
    else:
        nuevo_dias = 0

    if nitidez_sospechosa is None:
        # Sin suficiente historial todavía para evaluar (o sin imagen ese día) -- no es ni "sí" ni
        # "no", así que la racha se congela igual que `nuevo_dias` arriba.
        nuevo_dias_borroso = dias_borroso_previo
    elif nitidez_sospechosa:
        nuevo_dias_borroso = dias_borroso_previo + 1
    else:
        nuevo_dias_borroso = 0

    config_status = config_result["status"] if config_result else None
    nuevo_config_estado = _siguiente_estado_config(
        config_estado_previo, config_status, config_veredicto_humano,
    )
    if nuevo_config_estado == "incidencia" and config_estado_previo != "incidencia":
        nueva_config_incidencia_desde = fecha
    elif nuevo_config_estado == "ok":
        nueva_config_incidencia_desde = None
    else:
        nueva_config_incidencia_desde = config_incidencia_desde_previo

    with conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO historial_comparacion (
                camara_id, fecha,
                config_status, config_marca, config_diferencias, config_veredicto_humano,
                imagen_status, imagen_motivo, orb_inliers, orb_desplazamiento,
                fase_confianza, fase_desplazamiento,
                nitidez_actual, nitidez_mediana_historica, nitidez_mad_historica,
                nitidez_sospechosa,
                salud_varianza, salud_brillo, salud_sospechosa,
                orb_tx, orb_ty, orb_rotacion_deg, orb_escala,
                diaanterior_status, diaanterior_motivo,
                diaanterior_orb_desplazamiento, diaanterior_fase_desplazamiento,
                veredicto_humano, modo,
                log_ip, log_estado, log_motivo, tiempo_proceso_seg
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (camara_id, fecha) DO UPDATE SET
                config_status = EXCLUDED.config_status,
                config_marca = EXCLUDED.config_marca,
                config_diferencias = EXCLUDED.config_diferencias,
                config_veredicto_humano = EXCLUDED.config_veredicto_humano,
                imagen_status = EXCLUDED.imagen_status,
                imagen_motivo = EXCLUDED.imagen_motivo,
                orb_inliers = EXCLUDED.orb_inliers,
                orb_desplazamiento = EXCLUDED.orb_desplazamiento,
                fase_confianza = EXCLUDED.fase_confianza,
                fase_desplazamiento = EXCLUDED.fase_desplazamiento,
                nitidez_actual = EXCLUDED.nitidez_actual,
                nitidez_mediana_historica = EXCLUDED.nitidez_mediana_historica,
                nitidez_mad_historica = EXCLUDED.nitidez_mad_historica,
                nitidez_sospechosa = EXCLUDED.nitidez_sospechosa,
                salud_varianza = EXCLUDED.salud_varianza,
                salud_brillo = EXCLUDED.salud_brillo,
                salud_sospechosa = EXCLUDED.salud_sospechosa,
                orb_tx = EXCLUDED.orb_tx,
                orb_ty = EXCLUDED.orb_ty,
                orb_rotacion_deg = EXCLUDED.orb_rotacion_deg,
                orb_escala = EXCLUDED.orb_escala,
                diaanterior_status = EXCLUDED.diaanterior_status,
                diaanterior_motivo = EXCLUDED.diaanterior_motivo,
                diaanterior_orb_desplazamiento = EXCLUDED.diaanterior_orb_desplazamiento,
                diaanterior_fase_desplazamiento = EXCLUDED.diaanterior_fase_desplazamiento,
                veredicto_humano = EXCLUDED.veredicto_humano,
                modo = EXCLUDED.modo,
                log_ip = EXCLUDED.log_ip,
                log_estado = EXCLUDED.log_estado,
                log_motivo = EXCLUDED.log_motivo,
                tiempo_proceso_seg = EXCLUDED.tiempo_proceso_seg,
                corrida_ts = now()
            """,
            (
                camara_id, fecha,
                config_status,
                config_result["marca"] if config_result else None,
                Json(config_result["diferencias"]) if config_result else None,
                config_veredicto_humano,
                imagen_status,
                imagen_result["motivo"] if imagen_result else None,
                imagen_result["orb_inliers"] if imagen_result else None,
                imagen_result["orb_desp"] if imagen_result else None,
                imagen_result["fase_conf"] if imagen_result else None,
                imagen_result["fase_desp"] if imagen_result else None,
                imagen_result["nitidez_hoy"] if imagen_result else None,
                imagen_result["nitidez_mediana_hist"] if imagen_result else None,
                imagen_result["nitidez_mad_hist"] if imagen_result else None,
                nitidez_sospechosa,
                imagen_result["salud_varianza"] if imagen_result else None,
                imagen_result["salud_brillo"] if imagen_result else None,
                salud_sospechosa,
                imagen_result["orb_tx"] if imagen_result else None,
                imagen_result["orb_ty"] if imagen_result else None,
                imagen_result["orb_rotacion_deg"] if imagen_result else None,
                imagen_result["orb_escala"] if imagen_result else None,
                imagen_result["diaanterior_status"] if imagen_result else None,
                imagen_result["diaanterior_motivo"] if imagen_result else None,
                imagen_result["diaanterior_orb_desp"] if imagen_result else None,
                imagen_result["diaanterior_fase_desp"] if imagen_result else None,
                veredicto_humano,
                modo,
                log_info["ip"] if log_info else None,
                log_info["estado"] if log_info else None,
                log_info["motivo"] if log_info else None,
                log_info["tiempo_proceso"] if log_info else None,
            ),
        )
        cur.execute(
            """
            UPDATE perfil_camara
            SET estado_actual = %s,
                estado_desde = CASE WHEN estado_actual <> %s THEN %s ELSE estado_desde END,
                dias_no_concluyente_consecutivos = %s,
                dias_borroso_consecutivos = %s,
                n_confirmaciones_humanas = n_confirmaciones_humanas + %s,
                config_estado_actual = %s,
                config_incidencia_desde = %s,
                actualizado_en = now()
            WHERE id = %s
            """,
            (nuevo_estado, nuevo_estado, fecha, nuevo_dias, nuevo_dias_borroso,
             1 if veredicto_humano else 0, nuevo_config_estado, nueva_config_incidencia_desde,
             camara_id),
        )
    return nuevo_estado, nuevo_config_estado


def camaras_con_base_desactualizada(conn: psycopg2.extensions.connection) -> list[dict]:
    """Para `ventana_bases.py` -- reemplaza el escaneo de archivos `.desactualizada`."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT cliente, planta, servidor, camara
            FROM perfil_camara
            WHERE estado_actual = 'base_desactualizada'
            ORDER BY cliente, planta, servidor, camara
            """
        )
        return [
            {"cliente": c, "planta": p, "servidor": s, "camara": cam}
            for c, p, s, cam in cur.fetchall()
        ]


def crear_observacion(conn: psycopg2.extensions.connection, camara_id: int, texto: str) -> None:
    """Agrega una nota de contexto a la bitácora de la cámara (ROADMAP.md, "Observaciones por
    cámara"). Se captura desde `ventana_revision.py` al resolver un `REVISAR`, y desde
    `scripts/ventana_observaciones.py` (29/10/2026) para cualquier otra cámara."""
    with conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO observacion_camara (camara_id, texto) VALUES (%s, %s)",
            (camara_id, texto),
        )


def listar_camaras(conn: psycopg2.extensions.connection) -> list[dict]:
    """Catálogo completo de cámaras -- para la navegación tipo directorio (cliente/planta/
    servidor/cámara) de `scripts/ventana_observaciones.py` (ROADMAP.md, 29/10/2026)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, cliente, planta, servidor, camara
            FROM perfil_camara
            ORDER BY cliente, planta, servidor, camara
            """
        )
        return [
            {"id": id_, "cliente": cliente, "planta": planta, "servidor": servidor, "camara": camara}
            for id_, cliente, planta, servidor, camara in cur.fetchall()
        ]


def listar_camaras_con_estado(conn: psycopg2.extensions.connection, cliente: str) -> list[dict]:
    """Todas las cámaras de un cliente con su `estado_actual` -- el más reciente conocido, sin
    depender de que haya corrido el pipeline un día en particular -- para el reporte mensual
    completo de `scripts/reporte_mensual_cliente.py` (ROADMAP.md, 29/10/2026). A diferencia de
    `generar_reportes_del_dia()` (reporte diario), que solo ve cámaras con una fila en
    `historial_comparacion` de una fecha puntual, este reporte lista el catálogo completo del
    cliente sin importar su estado."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, planta, servidor, camara, estado_actual
            FROM perfil_camara
            WHERE cliente = %s
            ORDER BY planta, servidor, camara
            """,
            (cliente,),
        )
        columnas = [d.name for d in cur.description]
        return [dict(zip(columnas, f)) for f in cur.fetchall()]


def observaciones_del_mes_por_camara(
    conn: psycopg2.extensions.connection, camara_ids: list[int], anio: int, mes: int,
) -> dict[int, list[dict]]:
    """`{camara_id: [{"texto", "creado_en", "resuelta"}, ...]}` de las observaciones **creadas**
    en un mes calendario -- resueltas o no -- para el reporte mensual completo (ROADMAP.md,
    29/10/2026). A diferencia de `observaciones_para_reporte()` (ventana de 15 días contra la fecha
    de un reporte diario), aquí se listan todas las del mes sin importar si ya se resolvieron o
    hace cuánto (pedido del usuario: el reporte mensual es el registro completo del mes, no un
    estado "vigente")."""
    if not camara_ids:
        return {}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT camara_id, texto, creado_en, resuelta_en
            FROM observacion_camara
            WHERE camara_id = ANY(%s)
              AND EXTRACT(YEAR FROM creado_en) = %s AND EXTRACT(MONTH FROM creado_en) = %s
            ORDER BY creado_en
            """,
            (camara_ids, anio, mes),
        )
        resultado: dict[int, list[dict]] = {}
        for camara_id, texto, creado_en, resuelta_en in cur.fetchall():
            resultado.setdefault(camara_id, []).append(
                {"texto": texto, "creado_en": creado_en, "resuelta": resuelta_en is not None}
            )
        return resultado


def observaciones_vigentes_de_camara(
    conn: psycopg2.extensions.connection, camara_id: int, dias_resuelta_visible: int,
) -> list[dict]:
    """Observaciones vigentes de una sola cámara -- activas, o resueltas hace `dias_resuelta_visible`
    días o menos -- para `scripts/ventana_observaciones.py` (ROADMAP.md, 29/10/2026). Mismo criterio
    que `observaciones_para_reporte()`/el PDF, pero contra `CURRENT_DATE` (esta herramienta es en
    vivo, no reproduce un reporte pasado) y para una sola cámara en vez de un lote."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, texto, creado_en, resuelta_en
            FROM observacion_camara
            WHERE camara_id = %s
              AND (resuelta_en IS NULL OR resuelta_en::date >= CURRENT_DATE - %s::int)
            ORDER BY creado_en
            """,
            (camara_id, dias_resuelta_visible),
        )
        return [
            {"id": id_, "texto": texto, "creado_en": creado_en, "resuelta": resuelta_en is not None}
            for id_, texto, creado_en, resuelta_en in cur.fetchall()
        ]


def marcar_observacion_resuelta(conn: psycopg2.extensions.connection, observacion_id: int) -> None:
    """Cierra una observación de la bitácora -- primer lugar en todo el repo que de verdad escribe
    `resuelta_en` (ROADMAP.md, 29/10/2026, `scripts/ventana_observaciones.py`); hasta ahora quedaba
    listo para esto pero nada lo usaba (ver `observaciones_para_reporte`)."""
    with conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE observacion_camara SET resuelta_en = now() WHERE id = %s",
            (observacion_id,),
        )


def camaras_con_observaciones_vigentes(
    conn: psycopg2.extensions.connection, dias_resuelta_visible: int,
) -> set[int]:
    """`camara_id` de toda cámara con al menos una observación vigente hoy (activa, o resuelta hace
    `dias_resuelta_visible` días o menos) -- para el punto verde del árbol de
    `scripts/ventana_observaciones.py` (ROADMAP.md, 29/10/2026). A diferencia de
    `observaciones_para_reporte()`, aquí la ventana se cuenta contra `CURRENT_DATE` (hoy de verdad),
    no contra la fecha de un reporte -- esta herramienta es en vivo, no reproduce el pasado."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT camara_id FROM observacion_camara
            WHERE resuelta_en IS NULL OR resuelta_en::date >= CURRENT_DATE - %s::int
            """,
            (dias_resuelta_visible,),
        )
        return {camara_id for (camara_id,) in cur.fetchall()}


def camara_tiene_observacion_vigente(
    conn: psycopg2.extensions.connection, camara_id: int, dias_resuelta_visible: int,
) -> bool:
    """Igual que `camaras_con_observaciones_vigentes()` pero para una sola cámara -- para refrescar
    su punto verde en el árbol justo después de Guardar/Aceptar, sin volver a consultar las 300+
    cámaras completas."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM observacion_camara
                WHERE camara_id = %s
                  AND (resuelta_en IS NULL OR resuelta_en::date >= CURRENT_DATE - %s::int)
            )
            """,
            (camara_id, dias_resuelta_visible),
        )
        return cur.fetchone()[0]


def observaciones_para_reporte(
    conn: psycopg2.extensions.connection, camara_ids: list[int], fecha: datetime.date,
    dias_resuelta_visible: int,
) -> dict[int, list[dict]]:
    """`{camara_id: [{"texto", "creado_en", "resuelta"}, ...]}`, en orden cronológico -- para el
    reporte ejecutivo (ROADMAP.md, 29/10/2026). Trae las observaciones activas (`resuelta_en IS
    NULL`) más las resueltas en los últimos `dias_resuelta_visible` días -- después de esa ventana
    una observación resuelta deja de aparecer (acordado con el usuario, pedido 29/10/2026).

    La ventana se cuenta contra `fecha` (la fecha del **reporte**, no la fecha real en que se corre
    esto) para que un reporte de una fecha vieja se vea igual sin importar cuándo se regenere --
    mismo criterio que `dias_sin_resolver` en `datos_reporte._clasificar_falla()`.

    Hoy nada en este repo cierra una observación (ver `crear_observacion`), así que en la práctica
    esto siempre trae todas las que existan (todas con `resuelta_en IS NULL`) -- queda listo para
    cuando exista el programa de administración aparte que sí las cierre. Cámaras sin ninguna no
    aparecen como llave."""
    if not camara_ids:
        return {}
    limite = fecha - datetime.timedelta(days=dias_resuelta_visible)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT camara_id, texto, creado_en, resuelta_en
            FROM observacion_camara
            WHERE camara_id = ANY(%s) AND (resuelta_en IS NULL OR resuelta_en::date >= %s)
            ORDER BY camara_id, creado_en
            """,
            (camara_ids, limite),
        )
        resultado: dict[int, list[dict]] = {}
        for camara_id, texto, creado_en, resuelta_en in cur.fetchall():
            resultado.setdefault(camara_id, []).append(
                {"texto": texto, "creado_en": creado_en, "resuelta": resuelta_en is not None}
            )
        return resultado


def marcar_base_reemplazada(conn: psycopg2.extensions.connection, cliente: str, planta: str,
                             servidor: str, camara: str) -> None:
    """Confirma el reemplazo de una base: la cámara vuelve a verde (ROADMAP.md, sección 2.8), y
    queda marcada para promover su base a mediana en cuanto se junte suficiente historial fresco
    (ver ROADMAP.md, 26/10/2026, paso 3 -- `base_reemplazada_el`).

    También deja una nota corta en la bitácora (`observacion_camara`, pedido 29/10/2026) -- antes
    ningún llamador (`main.py`, `ui/ventana_bases.py`) dejaba rastro automático de un reemplazo, solo
    lo que el humano hubiera escrito a mano (si acaso) en el campo de observación opcional."""
    with conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE perfil_camara
            SET estado_actual = 'verde', estado_desde = CURRENT_DATE,
                base_reemplazada_el = CURRENT_DATE, actualizado_en = now()
            WHERE cliente = %s AND planta = %s AND servidor = %s AND camara = %s
            RETURNING id, base_reemplazada_el
            """,
            (cliente, planta, servidor, camara),
        )
        camara_id, fecha_reemplazo = cur.fetchone()
        cur.execute(
            "INSERT INTO observacion_camara (camara_id, texto) VALUES (%s, %s)",
            (camara_id, f"Base reemplazada el {fecha_reemplazo:%d/%m/%Y}."),
        )


def marcar_base_desactualizada_manual(conn: psycopg2.extensions.connection, cliente: str,
                                       planta: str, servidor: str, camara: str) -> None:
    """Marca la base como desactualizada desde una auditoría visual (`scripts/revisar_bases.py`),
    sin pasar por una comparación real -- no toca `historial_comparacion`, solo el semáforo."""
    with conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE perfil_camara
            SET estado_actual = 'base_desactualizada', estado_desde = CURRENT_DATE,
                actualizado_en = now()
            WHERE cliente = %s AND planta = %s AND servidor = %s AND camara = %s
            """,
            (cliente, planta, servidor, camara),
        )


def limpiar_base_reemplazada(conn: psycopg2.extensions.connection, cliente: str, planta: str,
                              servidor: str, camara: str) -> None:
    """Ya se promovió la base a mediana (ver `comparacion.image_compare.promover_base_a_mediana`)
    -- apaga la marca de "promoción pendiente"."""
    with conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE perfil_camara
            SET base_reemplazada_el = NULL, actualizado_en = now()
            WHERE cliente = %s AND planta = %s AND servidor = %s AND camara = %s
            """,
            (cliente, planta, servidor, camara),
        )


def guardar_estado_servicio_ia(
    conn: psycopg2.extensions.connection, cliente: str, planta: str, servidor: str,
    puerto: int, fecha: datetime.date, estado: str, motivo: str | None,
) -> str:
    """Upsert del catálogo/estado vivo de un servicio de IA (`servicio_ia`) + su registro del día
    (`historial_servicio_ia`), ROADMAP.md 27/10/2026. Regresa el estado anterior, para que
    `main.py` pueda avisar en consola cuando cambia (igual que `guardar_resultado`)."""
    with conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO servicio_ia (cliente, planta, servidor, puerto, estado_actual, estado_desde)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (cliente, planta, servidor, puerto) DO NOTHING
            """,
            (cliente, planta, servidor, puerto, estado, fecha),
        )
        cur.execute(
            """
            SELECT id, estado_actual FROM servicio_ia
            WHERE cliente = %s AND planta = %s AND servidor = %s AND puerto = %s
            """,
            (cliente, planta, servidor, puerto),
        )
        servicio_id, estado_previo = cur.fetchone()

        cur.execute(
            """
            UPDATE servicio_ia
            SET estado_actual = %s,
                estado_desde = CASE WHEN estado_actual <> %s THEN %s ELSE estado_desde END,
                actualizado_en = now()
            WHERE id = %s
            """,
            (estado, estado, fecha, servicio_id),
        )
        cur.execute(
            """
            INSERT INTO historial_servicio_ia (servicio_id, fecha, estado, motivo)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (servicio_id, fecha) DO UPDATE SET
                estado = EXCLUDED.estado,
                motivo = EXCLUDED.motivo
            """,
            (servicio_id, fecha, estado, motivo),
        )
    return estado_previo


MIN_MUESTRAS_CALIBRACION = 20  # ver recalcular_perfiles_estadisticos


def recalcular_perfiles_estadisticos(conn: psycopg2.extensions.connection) -> int:
    """Recalcula `mediana_desplazamiento`/`p95_desplazamiento` por cámara, a partir de su propio
    historial de desplazamientos "normales" (ROADMAP.md, 26/10/2026 -- conectar `umbral_para()`).

    Cuenta como "normal" un día donde `imagen_status = 'OK'` (el sistema ya dijo que no había
    problema), o donde un humano confirmó explícitamente que no lo había (`veredicto_humano =
    'bien'`, incluso si el sistema lo había marcado `REVISAR`) -- la evidencia real de qué tan
    ruidosa es cada cámara está justo en esos "REVISAR" que resultaron ser falsos positivos
    (confirmado con datos reales el 26/10/2026, ver `scripts/analizar_veredictos.py`). Se excluyen
    explícitamente los días confirmados como movimiento real (`mal`) o base desactualizada
    (`desactualizada`) -- esos no son "ruido normal", son justo lo que se quiere seguir detectando.

    Exige al menos `MIN_MUESTRAS_CALIBRACION` lecturas (ORB + fase combinadas) antes de confiar en
    el cálculo -- por debajo de eso, `perfil_camara.p95_desplazamiento` se deja sin tocar y
    `umbral_para()` sigue usando el umbral global para esa cámara.

    Pensado para correrse una vez al final de cada corrida de `main.py`, después de que todas las
    cámaras del día ya se guardaron -- nunca a mitad de la corrida del mismo día, para no calibrar
    con datos de hoy que todavía no se terminaron de verificar hoy mismo.

    Regresa cuántas cámaras quedaron (re)calibradas.
    """
    with conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM perfil_camara")
        camara_ids = [fila[0] for fila in cur.fetchall()]

        recalibradas = 0
        for camara_id in camara_ids:
            cur.execute(
                """
                SELECT orb_desplazamiento, fase_desplazamiento
                FROM historial_comparacion
                WHERE camara_id = %s
                  AND (imagen_status = 'OK' OR veredicto_humano = 'bien')
                  AND (veredicto_humano IS NULL OR veredicto_humano NOT IN ('mal', 'desactualizada'))
                """,
                (camara_id,),
            )
            valores = sorted(v for fila in cur.fetchall() for v in fila if v is not None)
            if len(valores) < MIN_MUESTRAS_CALIBRACION:
                continue

            mediana = statistics.median(valores)
            indice_p95 = max(0, int(len(valores) * 0.95) - 1)
            p95 = valores[indice_p95]

            cur.execute(
                """
                UPDATE perfil_camara
                SET mediana_desplazamiento = %s, p95_desplazamiento = %s,
                    ultimo_recalculo = CURRENT_DATE, actualizado_en = now()
                WHERE id = %s
                """,
                (mediana, p95, camara_id),
            )
            recalibradas += 1
    return recalibradas
