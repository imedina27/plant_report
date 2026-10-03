from datetime import date
from pathlib import Path

from config_compare import CHECK_PLANTS_ROOT, compare_camera_config
from image_compare import compare_camera_image


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


def main() -> None:
    raw = input("Fecha a procesar (formato ddmmyy, ej. 220926, o 'h' para hoy): ").strip()
    date_str = date.today().strftime("%d%m%y") if raw.lower() == "h" else raw

    camaras = _camaras_del_dia(date_str)
    if not camaras:
        print(f"No se encontraron archivos .json/.jpg para la fecha {date_str} en {CHECK_PLANTS_ROOT}")
        return

    print(f"Encontradas {len(camaras)} cámara(s) para la fecha {date_str}.")
    for cliente, planta, servidor, camara, json_path, jpg_path in camaras:
        partes = [f"{cliente}/{planta}/{servidor}/{camara}"]

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
        else:
            partes.append("imagen: SIN ARCHIVO")

        print("  - " + "  |  ".join(partes))


if __name__ == "__main__":
    main()
