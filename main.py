from log_sorter import sort_logs_for_date


def main() -> None:
    date_str = input("Fecha de los logs a ordenar (formato ddmmyy, ej. 180926): ").strip()
    sort_logs_for_date(date_str)


if __name__ == "__main__":
    main()
