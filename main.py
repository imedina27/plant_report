import argparse
import time
from datetime import date, datetime
from pathlib import Path

import db
from config_compare import CHECK_PLANTS_ROOT, compare_camera_config
from correo import enviar_reportes
from datos_reporte import generar_reportes_del_dia
from image_compare import base_path, compare_camera_image
from log_parse import parsear_log_servidor
from ventana_revision import VentanaRevision


def _camaras_del_dia(
    date_str: str, cliente: str | None = None,
) -> tuple[list[tuple[str, str, str, str, Path | None, Path | None]], dict[tuple[str, str, str], dict]]:
    """Encuentra cada cámara con `.json`, `.jpg` y/o entrada en el `.log` del servidor para esa fecha.

    Una cámara puede tener solo uno de los dos archivos (p. ej. si una fase de la descarga falló ese
    día) — se tolera y se deja esa fase sin procesar. Una cámara que falló por completo (ej. timeout
    de puerto) no tiene ni `.jpg` ni `.json`, pero sí aparece en el `.log` -- sin leerlo, esa cámara
    sería invisible para el resto del programa (ver ROADMAP.md, sección 3).

    `cliente`, si se da, acota el recorrido a esa carpeta de cliente únicamente (nombre exacto, tal
    cual aparece en `CHECK_PLANTS_ROOT`) -- evita recorrer el resto del árbol cuando solo interesa
    uno (ver `--cliente` en `main.py`).

    Regresa `(camaras, logs_por_servidor)`, donde `logs_por_servidor[(cliente, planta, servidor)]`
    es el resultado de `parsear_log_servidor()` para ese servidor (ya parseado una sola vez).
    """
    patron_cliente = cliente if cliente is not None else "*"

    encontradas: dict[tuple[str, str, str, str], dict[str, Path]] = {}
    for ext in ("json", "jpg"):
        for path in CHECK_PLANTS_ROOT.glob(f"{patron_cliente}/*/{date_str}/**/*.{ext}"):
            if path.stem.endswith("_ai"):
                continue
            cliente_encontrado, _mes, _fecha, planta, servidor = path.relative_to(CHECK_PLANTS_ROOT).parts[:5]
            camara = path.stem
            encontradas.setdefault((cliente_encontrado, planta, servidor, camara), {})[ext] = path

    logs_por_servidor: dict[tuple[str, str, str], dict] = {}
    for log_path in CHECK_PLANTS_ROOT.glob(f"{patron_cliente}/*/{date_str}/**/*.log"):
        partes = log_path.relative_to(CHECK_PLANTS_ROOT).parts
        if len(partes) != 6:
            continue  # es el resumen_[fecha].log del cliente, no el .log de un servidor puntual
        cliente_encontrado, _mes, _fecha, planta, servidor = partes[:5]
        log_servidor = parsear_log_servidor(log_path)
        logs_por_servidor[(cliente_encontrado, planta, servidor)] = log_servidor
        for camara in log_servidor:
            encontradas.setdefault((cliente_encontrado, planta, servidor, camara), {})

    camaras = [
        (cliente, planta, servidor, camara, archivos.get("json"), archivos.get("jpg"))
        for (cliente, planta, servidor, camara), archivos in sorted(encontradas.items())
    ]
    return camaras, logs_por_servidor


def _formatear_diagnostico(r: dict) -> str:
    def fmt(valor, sufijo=""):
        return f"{valor:.1f}{sufijo}" if valor is not None else "N/D"

    return (
        f"{r['motivo']}\n"
        f"ORB: {r['orb_inliers']} inliers, {fmt(r['orb_desp'], ' px')}      "
        f"Fase: confianza {fmt(r['fase_conf'])}, {fmt(r['fase_desp'], ' px')}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compara la configuración e imagen de cada cámara contra su base, y genera "
        "el reporte ejecutivo del día (ROADMAP.md).",
    )
    parser.add_argument(
        "--sin-interaccion", action="store_true",
        help="No abre la ventana de revisión; los REVISAR quedan solo en el log, sin bloquear. "
        "El reporte ejecutivo y el envío de correo se disparan automáticamente, sin preguntar.",
    )
    parser.add_argument(
        "--cliente",
        help="Procesa solo este cliente (nombre exacto de la carpeta bajo CHECK_PLANTS_ROOT, "
        "ej. AbInBev). Si se omite, procesa todos los clientes encontrados esa fecha.",
    )
    parser.add_argument(
        "--fecha",
        help="Fecha a procesar (formato ddmmyy, ej. 220926, o 'h' para hoy). Si se omite, se "
        "pregunta en la terminal -- para correr sin nadie presente (ej. tarea programada), "
        "combínalo con --sin-interaccion y da esta bandera también, si no, se queda esperando.",
    )
    args = parser.parse_args()

    raw = args.fecha if args.fecha else input("Fecha a procesar (formato ddmmyy, ej. 220926, o 'h' para hoy): ").strip()
    date_str = date.today().strftime("%d%m%y") if raw.lower() == "h" else raw
    fecha = datetime.strptime(date_str, "%d%m%y").date()

    camaras, logs_por_servidor = _camaras_del_dia(date_str, args.cliente)
    if not camaras:
        donde = CHECK_PLANTS_ROOT / args.cliente if args.cliente else CHECK_PLANTS_ROOT
        print(f"No se encontraron archivos .json/.jpg para la fecha {date_str} en {donde}")
        return

    print(f"Encontradas {len(camaras)} cámara(s) para la fecha {date_str}.")

    total = len(camaras)
    ventana = None if args.sin_interaccion else VentanaRevision()
    modo = "sin_interaccion" if args.sin_interaccion else "interactivo"
    conn = db.get_connection()

    for i, (cliente, planta, servidor, camara, json_path, jpg_path) in enumerate(camaras, start=1):
        etiqueta = f"{cliente}/{planta}/{servidor}/{camara}"
        if ventana is not None:
            ventana.mostrar_procesando(etiqueta, i - 1, total)

        partes = [etiqueta]
        perfil = db.obtener_camara(conn, cliente, planta, servidor, camara)
        log_info = logs_por_servidor.get((cliente, planta, servidor), {}).get(camara)

        config_result = None
        if json_path is not None:
            config_result = compare_camera_config(json_path, cliente, planta, servidor, camara)
            detalle = f" ({len(config_result['diferencias'])} campo(s))" if config_result["diferencias"] else ""
            partes.append(f"config[{config_result['marca'] or '?'}]: {config_result['status']}{detalle}")
        elif log_info and log_info["motivo"]:
            partes.append(f"config: SIN ARCHIVO ({log_info['motivo']})")
        else:
            partes.append("config: SIN ARCHIVO")

        imagen_result = None
        veredicto_humano = None
        if jpg_path is not None:
            ya_desactualizada = perfil["estado_actual"] == "base_desactualizada"
            imagen_result = compare_camera_image(
                jpg_path, cliente, planta, servidor, camara, ya_desactualizada,
            )
            detalle = f" ({imagen_result['motivo']})" if imagen_result["motivo"] else ""
            partes.append(f"imagen: {imagen_result['status']}{detalle}")

            if imagen_result["status"] == "REVISAR" and ventana is not None:
                if perfil["estado_actual"] == "rojo":
                    # Incidencia ya confirmada -- no se vuelve a preguntar (ROADMAP.md, sección 2.7)
                    partes.append("incidencia ya confirmada, sigue abierta")
                else:
                    diagnostico = _formatear_diagnostico(imagen_result)
                    ruta_base = base_path(cliente, planta, servidor, camara)
                    veredicto_humano, observacion = ventana.pedir_revision(
                        etiqueta, diagnostico, ruta_base, jpg_path,
                    )
                    if veredicto_humano == "desactualizada":
                        partes.append("base marcada como desactualizada")
                    elif veredicto_humano == "mal":
                        partes.append("CONFIRMADO: cámara movida")
                    else:
                        partes.append("marcado como falso positivo")
                    if observacion:
                        db.crear_observacion(conn, perfil["id"], observacion)
                        partes.append("observación guardada")
        elif log_info and log_info["motivo"]:
            partes.append(f"imagen: SIN ARCHIVO ({log_info['motivo']})")
        else:
            partes.append("imagen: SIN ARCHIVO")

        nuevo_estado = db.guardar_resultado(
            conn, perfil["id"], fecha, perfil["estado_actual"],
            perfil["dias_no_concluyente_consecutivos"],
            config_result, imagen_result, veredicto_humano, modo, log_info,
        )
        if nuevo_estado != perfil["estado_actual"]:
            partes.append(f"estado: {perfil['estado_actual']} -> {nuevo_estado}")

        print("  - " + "  |  ".join(partes))

    if ventana is not None:
        # Se cierra aquí, no al final -- lo que sigue (generar/enviar reporte) se contesta desde la
        # terminal, y dejar la ventana abierta sin hacer nada hacía pensar al usuario que seguía
        # procesando, tapando la terminal que en realidad ya estaba esperando su respuesta.
        ventana.mostrar_procesando("Corrida completa", total, total)
        time.sleep(1.0)
        ventana.cerrar()

    generar = args.sin_interaccion or input(
        "¿Generar el reporte ejecutivo de esta corrida? (s/n): "
    ).strip().lower().startswith("s")
    rutas_generadas: dict[str, Path] = {}
    if generar:
        print("Generando reportes ejecutivos...")
        rutas_generadas = generar_reportes_del_dia(conn, fecha, args.cliente)
        for cliente, ruta in rutas_generadas.items():
            print(f"  - {cliente}: {ruta}")
    else:
        print("Reportes ejecutivos omitidos por el usuario.")

    if rutas_generadas:
        enviar = args.sin_interaccion or input(
            "¿Enviar los reportes por correo? (s/n): "
        ).strip().lower().startswith("s")
        if enviar:
            print("Enviando correos...")
            for cliente, exito, motivo in enviar_reportes(rutas_generadas):
                print(f"  - {cliente}: enviado" if exito else f"  - {cliente}: FALLÓ ({motivo})")
        else:
            print("Envío de correos omitido por el usuario.")

    conn.close()


if __name__ == "__main__":
    main()
