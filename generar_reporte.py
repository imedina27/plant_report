"""Genera (y opcionalmente envía) el reporte ejecutivo de una fecha ya procesada, sin repetir la
comparación de cámaras ni la revisión humana -- usa lo que ya quedó guardado en
`perfil_camara`/`historial_comparacion` (ver `main.py`).

Pensado para cuando la corrida diaria ya se hizo (la revisión de `ventana_revision.py` incluida) pero
por lo que sea no se generó el PDF esa vez (ej. se contestó "no" sin querer), y correr `main.py` de
nuevo volvería a abrir la ventana de revisión para nada -- las cámaras ya resueltas no se vuelven a
preguntar, pero sí tendría que volver a leer y comparar todo.
"""

import argparse
from datetime import date, datetime

from integraciones.correo import enviar_reportes
from persistencia import db
from reporte.datos_reporte import generar_reportes_del_dia


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Genera el reporte ejecutivo de una fecha ya procesada, sin repetir la "
        "comparación de cámaras (ver main.py para la corrida diaria completa).",
        add_help=False,  # -h/--help se agrega abajo a mano, para que su ayuda salga en español
        # (el "-h" que agrega ArgumentParser solo no se puede traducir, siempre sale en inglés).
    )
    parser.add_argument(
        "-h", "--help", action="help", default=argparse.SUPPRESS,
        help="Muestra este mensaje de ayuda y termina.",
    )
    parser.add_argument(
        "--no-interaction", action="store_true",
        help="No pregunta nada; genera el reporte y envía el correo automáticamente.",
    )
    parser.add_argument(
        "--client",
        help="Genera (y envía) el reporte solo de este cliente (nombre exacto, ej. AbInBev). "
        "Si se omite, genera el de todos los clientes con datos esa fecha.",
    )
    parser.add_argument(
        "--date",
        help="Fecha ya procesada (formato ddmmyy, ej. 220926, o 'h' para hoy). Si se omite, se "
        "pregunta en la terminal.",
    )
    args = parser.parse_args()

    raw = args.date if args.date else input("Fecha ya procesada (formato ddmmyy, ej. 220926, o 'h' para hoy): ").strip()
    date_str = date.today().strftime("%d%m%y") if raw.lower() == "h" else raw
    fecha = datetime.strptime(date_str, "%d%m%y").date()

    conn = db.get_connection()
    print("Generando reportes ejecutivos...")
    rutas_generadas = generar_reportes_del_dia(conn, fecha, args.client)
    conn.close()

    if not rutas_generadas:
        donde = f" para {args.client} (revisa el nombre, ej. AbInBev)" if args.client else ""
        print(f"No se encontraron datos en la base de datos para la fecha {date_str}{donde}.")
        return

    for cliente, ruta in rutas_generadas.items():
        print(f"  - {cliente}: {ruta}")

    enviar = args.no_interaction or input(
        "¿Enviar los reportes por correo? (s/n): "
    ).strip().lower().startswith("s")
    if enviar:
        print("Enviando correos...")
        for cliente, exito, motivo in enviar_reportes(rutas_generadas):
            if exito:
                print(f"  - {cliente}: enviado" if motivo is None else f"  - {cliente}: {motivo}")
            else:
                print(f"  - {cliente}: FALLÓ ({motivo})")
    else:
        print("Envío de correos omitido por el usuario.")


if __name__ == "__main__":
    main()
