"""Captura una imagen directo de una cámara, para usarla como base limpia en
`ventana_bases.py` de Plant_Report (ROADMAP.md, sección 2.8) -- sin depender de que
la corrida automática del día traiga una imagen sin camión/montacargas en cuadro.

Uso:
    python captura.py <ip> <usuario> <password> <marca>

Carpeta pensada para copiarse sola a cada servidor (ver README.md) y correr ahí con
acceso directo a la cámara -- no a través de los túneles del programa externo de
revisión. Guarda en `images/<ip>/<timestamp>.jpg`, relativo a esta misma carpeta
(no al directorio desde donde se invoque); no sabe nada de cliente/planta/servidor/
cámara -- ese paso lo hace `ventana_bases.py`, eligiendo el archivo que este script
acaba de guardar.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import requests

from cameras import CAPTURA_POR_MARCA

CARPETA_IMAGENES = Path(__file__).parent / "images"


def main() -> None:
    parser = argparse.ArgumentParser(description="Captura una imagen directo de una cámara.")
    parser.add_argument("ip")
    parser.add_argument("usuario")
    parser.add_argument("password")
    parser.add_argument("marca", help=f"Una de: {', '.join(CAPTURA_POR_MARCA)}")
    args = parser.parse_args()

    capturar = CAPTURA_POR_MARCA.get(args.marca.upper())
    if capturar is None:
        print(f"Marca no soportada: {args.marca!r}. Soportadas: {', '.join(CAPTURA_POR_MARCA)}")
        sys.exit(1)

    try:
        contenido = capturar(args.ip, args.usuario, args.password)
    except (requests.exceptions.RequestException, ConnectionError) as error:
        print(f"No se pudo capturar la imagen de {args.ip}: {error}")
        sys.exit(1)

    if not contenido.startswith(b"\xff\xd8"):
        print(f"La respuesta de {args.ip} no es un JPEG válido -- revisa usuario/contraseña.")
        sys.exit(1)

    # ":" no es válido en nombres de carpeta en Windows -- pasa con ip:puerto (ej. túneles locales)
    carpeta_ip = CARPETA_IMAGENES / args.ip.replace(":", "_")
    carpeta_ip.mkdir(parents=True, exist_ok=True)
    salida = carpeta_ip / f"{datetime.now():%Y%m%d_%H%M%S}.jpg"
    salida.write_bytes(contenido)
    print(f"OK -- {len(contenido) / 1024:.0f} KB guardados en {salida}")


if __name__ == "__main__":
    main()
