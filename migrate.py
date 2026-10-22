"""Aplica, en orden, los archivos .sql de migrations/ que todavía no se hayan corrido."""

from __future__ import annotations

from pathlib import Path

from db import get_connection

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def main() -> None:
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    nombre_archivo TEXT PRIMARY KEY,
                    aplicada_en    TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            cur.execute("SELECT nombre_archivo FROM schema_migrations")
            aplicadas = {fila[0] for fila in cur.fetchall()}

            for ruta in sorted(MIGRATIONS_DIR.glob("*.sql")):
                if ruta.name in aplicadas:
                    print(f"ya aplicada -- {ruta.name}")
                    continue
                cur.execute(ruta.read_text(encoding="utf-8"))
                cur.execute(
                    "INSERT INTO schema_migrations (nombre_archivo) VALUES (%s)", (ruta.name,)
                )
                print(f"OK -- {ruta.name}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
