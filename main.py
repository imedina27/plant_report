from datetime import date

from config_compare import CHECK_PLANTS_ROOT, compare_camera_config


def main() -> None:
    raw = input("Fecha a procesar (formato ddmmyy, ej. 220926, o 'h' para hoy): ").strip()
    date_str = date.today().strftime("%d%m%y") if raw.lower() == "h" else raw
    json_paths = sorted(CHECK_PLANTS_ROOT.glob(f"*/*/{date_str}/**/*.json"))
    if not json_paths:
        print(f"No se encontraron archivos .json para la fecha {date_str} en {CHECK_PLANTS_ROOT}")
        return

    print(f"Encontrados {len(json_paths)} archivo(s) .json para la fecha {date_str}.")
    for json_path in json_paths:
        cliente, _mes, _fecha, planta, servidor = json_path.relative_to(CHECK_PLANTS_ROOT).parts[:5]
        camara = json_path.stem
        result = compare_camera_config(json_path, cliente, planta, servidor, camara)
        detalle = f" ({len(result['diferencias'])} campo(s))" if result["diferencias"] else ""
        print(f"  - {cliente}/{planta}/{servidor}/{camara} [{result['marca'] or '?'}]: {result['status']}{detalle}")


if __name__ == "__main__":
    main()
