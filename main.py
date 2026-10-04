import argparse
import time
from datetime import date
from pathlib import Path

from config_compare import CHECK_PLANTS_ROOT, compare_camera_config
from image_compare import base_path, compare_camera_image, marcar_base_desactualizada
from ventana_revision import VentanaRevision


def _camaras_del_dia(date_str: str) -> list[tuple[str, str, str, str, Path | None, Path | None]]:
    """Encuentra cada cámara con `.json` y/o `.jpg` para esa fecha.

    Una cámara puede tener solo uno de los dos archivos (p. ej. si una fase de
    la descarga falló ese día) — se tolera y se deja esa fase sin procesar.
    """
    encontradas: dict[tuple[str, str, str, str], dict[str, Path]] = {}
    for ext in ("json", "jpg"):
        for path in CHECK_PLANTS_ROOT.glob(f"*/*/{date_str}/**/*.{ext}"):
            if path.stem.endswith("_ai"):
                continue
            cliente, _mes, _fecha, planta, servidor = path.relative_to(CHECK_PLANTS_ROOT).parts[:5]
            camara = path.stem
            encontradas.setdefault((cliente, planta, servidor, camara), {})[ext] = path

    return [
        (cliente, planta, servidor, camara, archivos.get("json"), archivos.get("jpg"))
        for (cliente, planta, servidor, camara), archivos in sorted(encontradas.items())
    ]


def _formatear_diagnostico(r: dict) -> str:
    def fmt(valor, sufijo=""):
        return f"{valor:.1f}{sufijo}" if valor is not None else "N/D"

    return (
        f"{r['motivo']}\n"
        f"ORB: {r['orb_inliers']} inliers, {fmt(r['orb_desp'], ' px')}      "
        f"Fase: confianza {fmt(r['fase_conf'])}, {fmt(r['fase_desp'], ' px')}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--sin-interaccion", action="store_true",
        help="No abre la ventana de revisión; los REVISAR quedan solo en el log, sin bloquear.",
    )
    args = parser.parse_args()

    raw = input("Fecha a procesar (formato ddmmyy, ej. 220926, o 'h' para hoy): ").strip()
    date_str = date.today().strftime("%d%m%y") if raw.lower() == "h" else raw

    camaras = _camaras_del_dia(date_str)
    if not camaras:
        print(f"No se encontraron archivos .json/.jpg para la fecha {date_str} en {CHECK_PLANTS_ROOT}")
        return

    print(f"Encontradas {len(camaras)} cámara(s) para la fecha {date_str}.")

    total = len(camaras)
    ventana = None if args.sin_interaccion else VentanaRevision()

    for i, (cliente, planta, servidor, camara, json_path, jpg_path) in enumerate(camaras, start=1):
        etiqueta = f"{cliente}/{planta}/{servidor}/{camara}"
        if ventana is not None:
            ventana.mostrar_procesando(etiqueta, i - 1, total)

        partes = [etiqueta]

        if json_path is not None:
            r = compare_camera_config(json_path, cliente, planta, servidor, camara)
            detalle = f" ({len(r['diferencias'])} campo(s))" if r["diferencias"] else ""
            partes.append(f"config[{r['marca'] or '?'}]: {r['status']}{detalle}")
        else:
            partes.append("config: SIN ARCHIVO")

        if jpg_path is not None:
            r = compare_camera_image(jpg_path, cliente, planta, servidor, camara)
            detalle = f" ({r['motivo']})" if r["motivo"] else ""
            partes.append(f"imagen: {r['status']}{detalle}")

            if r["status"] == "REVISAR" and ventana is not None:
                diagnostico = _formatear_diagnostico(r)
                ruta_base = base_path(cliente, planta, servidor, camara)
                accion = ventana.pedir_revision(etiqueta, diagnostico, ruta_base, jpg_path)
                if accion == "desactualizada":
                    marcar_base_desactualizada(cliente, planta, servidor, camara)
                    partes.append("base marcada como desactualizada")
                elif accion == "mal":
                    partes.append("CONFIRMADO: cámara movida")
                else:
                    partes.append("marcado como falso positivo")
        else:
            partes.append("imagen: SIN ARCHIVO")

        print("  - " + "  |  ".join(partes))

    if ventana is not None:
        ventana.mostrar_procesando("Corrida completa", total, total)
        time.sleep(1.0)
        ventana.cerrar()


if __name__ == "__main__":
    main()
