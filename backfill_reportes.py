"""Corre la comparación y el reporte ejecutivo para un rango de fechas pasadas, **sin tocar la base
de datos** -- solo para revisar resultados sobre un mes completo de datos reales (ej. detectar
cámaras/servidores que necesiten atención) sin contaminar el historial oficial ni disparar correos.

Reutiliza la lógica real (`db._siguiente_estado()`, `datos_reporte._clasificar_falla()`) pero
mantiene el estado de cada cámara en memoria (un dict, no Postgres) mientras recorre los días en
orden -- así el semáforo (rojo/ámbar/morado) se calcula igual que en producción, día tras día,
sin persistir nada al terminar.

Aviso importante (ver conversación): las bases de configuración/imagen se crearon el 21/10/2026 a
partir de datos de ese día -- comparar días anteriores contra ellas puede marcar cambios que son
reales (la cámara sí se veía/configuraba distinto entonces) pero no indican un problema de esos
días, solo que el punto de referencia es posterior. Es ruido esperado del backfill, no necesariamente
algo que corregir.

Uso: pipenv run python backfill_reportes.py
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from config_compare import compare_camera_config
from datos_reporte import _clasificar_falla
from db import _siguiente_estado
from image_compare import compare_camera_image
from main import _camaras_del_dia
from monit_client import temperaturas_promedio_dia, uso_disco_actual
from reporte_ejecutivo import ResumenServidor, construir_pdf

FECHA_INICIO = date(2026, 10, 1)
FECHA_FIN = date.today()

SALIDA_ROOT = Path(__file__).parent / "Reportes_Backfill"


def main() -> None:
    # (cliente, planta, servidor, camara) -> {"estado_actual", "dias_no_concluyente_consecutivos"}
    perfiles: dict[tuple[str, str, str, str], dict] = {}
    resumen_por_dia: list[tuple[date, int, int]] = []  # (fecha, total_camaras, total_fallas)

    fecha = FECHA_INICIO
    while fecha <= FECHA_FIN:
        date_str = f"{fecha:%d%m%y}"
        camaras, logs_por_servidor = _camaras_del_dia(date_str)
        if not camaras:
            fecha += timedelta(days=1)
            continue

        # (cliente, planta, servidor) -> lista de filas estilo datos_reporte._resumen_servidor
        filas_por_servidor: dict[tuple[str, str, str], list[dict]] = {}

        for cliente, planta, servidor, camara, json_path, jpg_path in camaras:
            clave = (cliente, planta, servidor, camara)
            perfil = perfiles.setdefault(
                clave, {"estado_actual": "verde", "dias_no_concluyente_consecutivos": 0},
            )
            log_info = logs_por_servidor.get((cliente, planta, servidor), {}).get(camara)

            config_result = (
                compare_camera_config(json_path, cliente, planta, servidor, camara)
                if json_path is not None else None
            )

            imagen_result = None
            if jpg_path is not None:
                ya_desactualizada = perfil["estado_actual"] == "base_desactualizada"
                imagen_result = compare_camera_image(
                    jpg_path, cliente, planta, servidor, camara, ya_desactualizada,
                )

            imagen_status = imagen_result["status"] if imagen_result else None
            nuevo_estado = _siguiente_estado(perfil["estado_actual"], imagen_status, None)
            nuevos_dias = (
                perfil["dias_no_concluyente_consecutivos"] + 1
                if imagen_status == "NO CONCLUYENTE" else 0
            )
            perfiles[clave] = {"estado_actual": nuevo_estado, "dias_no_concluyente_consecutivos": nuevos_dias}

            filas_por_servidor.setdefault((cliente, planta, servidor), []).append({
                "camara": camara,
                "estado_actual": nuevo_estado,
                "dias_no_concluyente_consecutivos": nuevos_dias,
                "imagen_motivo": imagen_result["motivo"] if imagen_result else None,
                "log_estado": log_info["estado"] if log_info else None,
                "log_motivo": log_info["motivo"] if log_info else None,
            })

        # Arma un PDF por cliente, igual que datos_reporte.generar_reportes_del_dia pero en memoria.
        por_cliente: dict[str, list[ResumenServidor]] = {}
        total_camaras_dia = total_fallas_dia = 0
        for (cliente, planta, servidor), filas in filas_por_servidor.items():
            fallas = [
                f for f in (_clasificar_falla(f, cliente, planta, servidor, fecha) for f in filas)
                if f is not None
            ]
            camaras_ok = sum(
                1 for f in filas if f["estado_actual"] == "verde" and f["log_estado"] != "ERROR"
            )
            temperaturas = temperaturas_promedio_dia(servidor, fecha)
            resumen = ResumenServidor(
                nombre=servidor, planta=planta,
                cpu=temperaturas["cpu"] if temperaturas else None,
                gpu=temperaturas["gpu"] if temperaturas else None,
                discos=uso_disco_actual(servidor),
                camaras_totales=len(filas), camaras_ok=camaras_ok, fallas=fallas,
            )
            por_cliente.setdefault(cliente, []).append(resumen)
            total_camaras_dia += len(filas)
            total_fallas_dia += len(fallas)

        for cliente, servidores in por_cliente.items():
            carpeta = SALIDA_ROOT / cliente
            carpeta.mkdir(parents=True, exist_ok=True)
            construir_pdf(cliente, fecha, servidores, carpeta / f"{fecha:%d%m%Y}_{cliente}.pdf")

        resumen_por_dia.append((fecha, total_camaras_dia, total_fallas_dia))
        print(f"{fecha:%d/%m/%Y}: {total_camaras_dia} cámaras, {total_fallas_dia} con falla"
              f" ({', '.join(por_cliente)})")

        fecha += timedelta(days=1)

    print(f"\nPDFs guardados en: {SALIDA_ROOT}")
    print("\nResumen del mes:")
    for fecha, total, fallas in resumen_por_dia:
        print(f"  {fecha:%d/%m}: {total} cámaras, {fallas} con falla")


if __name__ == "__main__":
    main()
