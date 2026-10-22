"""Persistencia en PostgreSQL (Fase 3, ROADMAP.md sección "Persistencia en base de datos").

`perfil_camara` es el catálogo de cámaras y, a la vez, su estado vivo (semáforo, sección 2.7) y su
perfil estadístico. `historial_comparacion` es el registro crudo, una fila por cámara por día.
"""

from __future__ import annotations

import datetime
import os

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
            SELECT id, estado_actual, dias_no_concluyente_consecutivos
            FROM perfil_camara
            WHERE cliente = %s AND planta = %s AND servidor = %s AND camara = %s
            """,
            (cliente, planta, servidor, camara),
        )
        id_, estado_actual, dias = cur.fetchone()
        return {"id": id_, "estado_actual": estado_actual, "dias_no_concluyente_consecutivos": dias}


def _siguiente_estado(estado_actual: str, imagen_status: str | None, veredicto_humano: str | None) -> str:
    """Máquina de estados del semáforo (ROADMAP.md, sección 2.7)."""
    if veredicto_humano == "bien":
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
        return "verde"
    if imagen_status == "REVISAR":
        return "morado"
    if imagen_status == "NO CONCLUYENTE":
        return "amarillo"
    return estado_actual


def guardar_resultado(
    conn: psycopg2.extensions.connection, camara_id: int, fecha: datetime.date,
    estado_actual_previo: str, dias_no_concl_previo: int,
    config_result: dict | None, imagen_result: dict | None,
    veredicto_humano: str | None, modo: str,
    log_info: dict | None = None,
) -> str:
    """Escribe el resultado de una cámara (upsert por día) y actualiza su estado vivo.

    Se llama una vez por cámara, justo después de resolverla -- no en lote al final de la corrida
    (ver ROADMAP.md, sección 3): así un fallo de conexión a media corrida solo pierde la cámara en
    curso, no el veredicto humano ya dado en las cámaras anteriores.

    `log_info` viene de `log_parse.parsear_log_servidor()`: el diagnóstico de conexión/captura del
    `.log` del servidor para esta cámara (si el programa externo de revisión logró procesarla ese
    día, y si no, por qué) -- independiente de si Fase 1/2 encontraron algo que comparar.
    """
    imagen_status = imagen_result["status"] if imagen_result else None
    nuevo_estado = _siguiente_estado(estado_actual_previo, imagen_status, veredicto_humano)
    nuevo_dias = dias_no_concl_previo + 1 if imagen_status == "NO CONCLUYENTE" else 0

    with conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO historial_comparacion (
                camara_id, fecha,
                config_status, config_marca, config_diferencias,
                imagen_status, imagen_motivo, orb_inliers, orb_desplazamiento,
                fase_confianza, fase_desplazamiento,
                veredicto_humano, modo,
                log_ip, log_estado, log_motivo, tiempo_proceso_seg
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (camara_id, fecha) DO UPDATE SET
                config_status = EXCLUDED.config_status,
                config_marca = EXCLUDED.config_marca,
                config_diferencias = EXCLUDED.config_diferencias,
                imagen_status = EXCLUDED.imagen_status,
                imagen_motivo = EXCLUDED.imagen_motivo,
                orb_inliers = EXCLUDED.orb_inliers,
                orb_desplazamiento = EXCLUDED.orb_desplazamiento,
                fase_confianza = EXCLUDED.fase_confianza,
                fase_desplazamiento = EXCLUDED.fase_desplazamiento,
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
                config_result["status"] if config_result else None,
                config_result["marca"] if config_result else None,
                Json(config_result["diferencias"]) if config_result else None,
                imagen_status,
                imagen_result["motivo"] if imagen_result else None,
                imagen_result["orb_inliers"] if imagen_result else None,
                imagen_result["orb_desp"] if imagen_result else None,
                imagen_result["fase_conf"] if imagen_result else None,
                imagen_result["fase_desp"] if imagen_result else None,
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
                n_confirmaciones_humanas = n_confirmaciones_humanas + %s,
                actualizado_en = now()
            WHERE id = %s
            """,
            (nuevo_estado, nuevo_estado, fecha, nuevo_dias, 1 if veredicto_humano else 0, camara_id),
        )
    return nuevo_estado


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
    cámara"). Se captura desde `ventana_revision.py` al resolver un `REVISAR`; cerrarlas o editarlas
    queda para el programa de administración aparte (fuera de este repo)."""
    with conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO observacion_camara (camara_id, texto) VALUES (%s, %s)",
            (camara_id, texto),
        )


def marcar_base_reemplazada(conn: psycopg2.extensions.connection, cliente: str, planta: str,
                             servidor: str, camara: str) -> None:
    """Confirma el reemplazo de una base: la cámara vuelve a verde (ROADMAP.md, sección 2.8)."""
    with conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE perfil_camara
            SET estado_actual = 'verde', estado_desde = CURRENT_DATE, actualizado_en = now()
            WHERE cliente = %s AND planta = %s AND servidor = %s AND camara = %s
            """,
            (cliente, planta, servidor, camara),
        )
