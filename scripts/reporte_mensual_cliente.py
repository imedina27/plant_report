"""Genera el reporte mensual completo de un cliente (ROADMAP.md, 29/10/2026): a diferencia de
`generar_reporte.py` (reporte diario, solo cámaras con falla de un día ya procesado), este lista
TODAS las cámaras del cliente sin importar su estado, con sus observaciones creadas ese mes --
resueltas o no. Reporte manual, a petición del cliente -- no se envía por correo ni se automatiza.
"""

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from persistencia import db
from reporte.datos_reporte import generar_reporte_mensual_cliente


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Genera el reporte mensual completo de un cliente (todas sus cámaras, "
        "observaciones creadas ese mes).",
        add_help=False,  # -h/--help se agrega abajo a mano, para que su ayuda salga en español
    )
    parser.add_argument(
        "-h", "--help", action="help", default=argparse.SUPPRESS,
        help="Muestra este mensaje de ayuda y termina.",
    )
    parser.add_argument(
        "--client", required=True,
        help="Nombre exacto del cliente (ej. AbInBev).",
    )
    parser.add_argument(
        "--month", type=int,
        help="Mes a reportar (1-12). Si se omite, el mes en curso.",
    )
    parser.add_argument(
        "--year", type=int,
        help="Año a reportar (ej. 2026). Si se omite, el año en curso.",
    )
    args = parser.parse_args()

    hoy = date.today()
    mes = args.month or hoy.month
    anio = args.year or hoy.year

    conn = db.get_connection()
    ruta = generar_reporte_mensual_cliente(conn, args.client, anio, mes)
    conn.close()

    if ruta is None:
        print(f"No se encontró el cliente '{args.client}' en el catálogo (revisa el nombre, ej. AbInBev).")
        return

    print(f"Reporte generado: {ruta}")


if __name__ == "__main__":
    main()
