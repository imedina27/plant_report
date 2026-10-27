"""Set de validación: compara las señales calculadas contra el veredicto humano real (ROADMAP.md,
26/10/2026 -- punto 6 del plan de mejoras a image_compare.py).

Cada vez que `ventana_revision.py` pide una decisión humana, ese veredicto queda guardado en
`historial_comparacion.veredicto_humano` junto con todas las señales que se calcularon ese día --
sin que nadie lo haya diseñado para esto, es ya el arranque de un set de validación real de
producción. Este script no entrena ni ajusta nada solo -- imprime los datos agrupados y con
estadísticas básicas para que una persona decida si vale la pena recalibrar algo.

Pensado para correrse cada cierto tiempo (ej. semanal) conforme se acumulen más veredictos,
especialmente de las señales nuevas del 26/10/2026 (nitidez, salud, día anterior, rotación/escala)
que todavía no tienen historial real al momento de escribir esto.

Uso: pipenv run python scripts/analizar_veredictos.py
"""

from __future__ import annotations

import sys
import statistics
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from persistencia import db

_COLUMNAS = """
    p.cliente, p.planta, p.servidor, p.camara, h.fecha, h.imagen_status, h.imagen_motivo,
    h.orb_inliers, h.orb_desplazamiento, h.fase_confianza, h.fase_desplazamiento,
    h.nitidez_actual, h.nitidez_mediana_historica, h.nitidez_sospechosa,
    h.salud_varianza, h.salud_brillo, h.salud_sospechosa,
    h.orb_rotacion_deg, h.orb_escala,
    h.diaanterior_status, h.diaanterior_orb_desplazamiento,
    h.veredicto_humano
"""


def _traer_veredictos(conn) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(f"""
            SELECT {_COLUMNAS}
            FROM historial_comparacion h JOIN perfil_camara p ON p.id = h.camara_id
            WHERE h.veredicto_humano IS NOT NULL
            ORDER BY h.veredicto_humano, h.fecha
        """)
        columnas = [desc[0] for desc in cur.description]
        return [dict(zip(columnas, fila)) for fila in cur.fetchall()]


def _resumen_numerico(etiqueta: str, valores: list[float]) -> None:
    valores = [v for v in valores if v is not None]
    if not valores:
        print(f"    {etiqueta}: sin datos")
        return
    print(
        f"    {etiqueta}: n={len(valores)}  min={min(valores):.1f}  mediana={statistics.median(valores):.1f}  "
        f"max={max(valores):.1f}"
    )


def main() -> None:
    conn = db.get_connection()
    try:
        filas = _traer_veredictos(conn)
    finally:
        conn.close()

    if not filas:
        print("Todavía no hay veredictos humanos guardados.")
        return

    fechas = sorted({f["fecha"] for f in filas})
    print(f"Total de veredictos: {len(filas)}  (de {fechas[0]} a {fechas[-1]})\n")

    por_veredicto: dict[str, list[dict]] = {}
    for f in filas:
        por_veredicto.setdefault(f["veredicto_humano"], []).append(f)

    for veredicto, grupo in sorted(por_veredicto.items(), key=lambda kv: -len(kv[1])):
        print(f"=== {veredicto} (n={len(grupo)}) ===")
        _resumen_numerico("orb_desplazamiento", [f["orb_desplazamiento"] for f in grupo])
        _resumen_numerico("orb_inliers", [f["orb_inliers"] for f in grupo])
        _resumen_numerico("fase_desplazamiento", [f["fase_desplazamiento"] for f in grupo])
        con_nitidez = [f for f in grupo if f["nitidez_actual"] is not None]
        if con_nitidez:
            print(f"    con dato de nitidez: {len(con_nitidez)}")
        con_dia_anterior = [f for f in grupo if f["diaanterior_status"] is not None]
        if con_dia_anterior:
            print(f"    con dato de día anterior: {len(con_dia_anterior)}")
        if veredicto in ("mal", "desactualizada"):
            print("    Detalle (son pocos, vale la pena verlos uno por uno):")
            for f in grupo:
                print(
                    f"      {f['cliente']}/{f['planta']}/{f['servidor']}/{f['camara']} ({f['fecha']}): "
                    f"{f['imagen_status']} -- {f['imagen_motivo']} -- "
                    f"ORB {f['orb_inliers']} inliers / {f['orb_desplazamiento']} px -- "
                    f"Fase conf {f['fase_confianza']} / {f['fase_desplazamiento']} px"
                )
        print()


if __name__ == "__main__":
    main()
