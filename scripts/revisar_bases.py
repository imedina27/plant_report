"""Auditoría visual rápida de bases de imagen ya existentes (ROADMAP.md, 27/10/2026).

Muestra, cámara por cámara, la base real de un servidor elegido (`IMAGE_BASE_ROOT`) y deja
marcarla como "base_desactualizada" con un clic si se ve mal -- sin pasar por una comparación
real, solo para filtrar visualmente después de un cambio grande como la separación base/mediana
del 27/10/2026.

"Bien" no escribe nada -- ni siquiera recuerda qué ya se revisó; si se corre de nuevo sobre el
mismo servidor, se vuelve a ver todo desde el principio (decisión explícita, más simple). "Base
Desactualizada" marca `perfil_camara.estado_actual = 'base_desactualizada'` (mismo estado que usa
el flujo normal, `ui/ventana_bases.py` ya lo recoge) y deja una nota en la bitácora de la cámara.

Las cámaras que YA están en `base_desactualizada` se saltan solas -- no tiene caso re-marcarlas.

Uso: pipenv run python scripts/revisar_bases.py --client AbInBev --plant ZACATECAS --server QLYMSPROD01
     pipenv run python scripts/revisar_bases.py   (sin banderas: lista las combinaciones disponibles)
"""

from __future__ import annotations

import argparse
import sys
import tkinter as tk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from comparacion.image_compare import IMAGE_BASE_ROOT, base_path
from persistencia import db
from ui.ventana_revision import (
    AZUL,
    DARK_THEME,
    FUENTE,
    LIGHT_THEME,
    MAX_ANCHO_PANEL,
    OK,
    _cargar_para_tk,
    _oscurecer_titlebar,
    _tema_oscuro_del_sistema,
)

NOTA_DESACTUALIZADA = "Marcada como desactualizada desde auditoría visual (scripts/revisar_bases.py)."


def _combinaciones_disponibles() -> list[tuple[str, str, str]]:
    combinaciones = {
        path.relative_to(IMAGE_BASE_ROOT).parts[:3]
        for path in IMAGE_BASE_ROOT.glob("*/*/*/*.jpg")
    }
    return sorted(combinaciones)


class _VentanaRevisarBase:
    """Ventana mínima de un solo panel -- reutiliza tema/paleta/helpers de
    `ui.ventana_revision`, pero no la clase completa (pensada para base+actual+observación,
    más de lo que hace falta aquí)."""

    def __init__(self) -> None:
        oscuro = _tema_oscuro_del_sistema()
        self.theme = DARK_THEME if oscuro else LIGHT_THEME
        t = self.theme
        self.root = tk.Tk()
        self.root.title("Revisar Bases — Quantum Labs")
        self.root.configure(bg=t["background"])
        self.root.geometry("760x720")
        _oscurecer_titlebar(self.root, oscuro)
        self._accion = tk.StringVar(value="")
        self._img_ref: tk.PhotoImage | None = None

    def pedir_veredicto(self, titulo: str, ruta_base: Path, indice: int, total: int) -> str:
        t = self.theme
        for widget in self.root.winfo_children():
            widget.destroy()

        tk.Label(self.root, text=f"{indice} de {total}", font=(FUENTE, 10),
                 bg=t["background"], fg=t["tenue"]).pack(pady=(14, 0))
        tk.Label(self.root, text=titulo, font=(FUENTE, 16, "bold"),
                 bg=t["background"], fg=t["text"]).pack(pady=(2, 12))

        self._img_ref = _cargar_para_tk(ruta_base, MAX_ANCHO_PANEL)
        marco = tk.Frame(self.root, bg=t["frame_background"],
                          highlightbackground=t["border"], highlightthickness=1)
        marco.pack()
        tk.Label(marco, image=self._img_ref, bg=t["frame_background"]).pack(padx=4, pady=4)

        botones = tk.Frame(self.root, bg=t["background"])
        botones.pack(pady=20)
        self._accion.set("")
        tk.Button(botones, text="Bien", bg=OK, fg="white", activebackground=OK,
                  font=(FUENTE, 12, "bold"), width=16, relief="flat", bd=0,
                  command=lambda: self._accion.set("bien")).grid(row=0, column=0, padx=10)
        tk.Button(botones, text="Base Desactualizada", bg=AZUL, fg="white", activebackground=AZUL,
                  font=(FUENTE, 12, "bold"), width=20, relief="flat", bd=0,
                  command=lambda: self._accion.set("desactualizada")).grid(row=0, column=1, padx=10)

        self.root.update()
        self.root.wait_variable(self._accion)
        return self._accion.get()

    def cerrar(self) -> None:
        self.root.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Auditoría visual rápida de las bases de imagen de un servidor -- ver docstring.",
    )
    parser.add_argument("--client", help="Cliente exacto (carpeta bajo IMAGE_BASE_ROOT).")
    parser.add_argument("--plant", help="Planta exacta.")
    parser.add_argument("--server", help="Servidor exacto.")
    args = parser.parse_args()

    combinaciones = _combinaciones_disponibles()
    if not (args.client and args.plant and args.server):
        print("Faltan --client/--plant/--server. Combinaciones disponibles:\n")
        for cliente, planta, servidor in combinaciones:
            print(f"  --client {cliente} --plant {planta} --server {servidor}")
        return

    # Windows no distingue mayúsculas/minúsculas en rutas de archivo, pero Postgres sí -- un typo de
    # mayúsculas aquí (ej. "AbINBEV" en vez de "AbInBev") encuentra las fotos igual (mismo archivo en
    # disco) pero crea una cámara "fantasma" aparte en la base de datos, divorciada de la real
    # (ROADMAP.md, 28/10/2026). Se normaliza contra la capitalización real encontrada en disco antes
    # de tocar la base de datos.
    coincidencia = next(
        (c for c in combinaciones
         if c[0].lower() == args.client.lower() and c[1].lower() == args.plant.lower()
         and c[2].lower() == args.server.lower()),
        None,
    )
    if coincidencia is None:
        print(f"No se encontró {args.client}/{args.plant}/{args.server} (revisando mayúsculas/"
              "minúsculas). Combinaciones disponibles:\n")
        for cliente, planta, servidor in combinaciones:
            print(f"  --client {cliente} --plant {planta} --server {servidor}")
        return
    cliente, planta, servidor = coincidencia
    if (cliente, planta, servidor) != (args.client, args.plant, args.server):
        print(f"Aviso: se normalizó a --client {cliente} --plant {planta} --server {servidor}")
    args.client, args.plant, args.server = cliente, planta, servidor

    carpeta = IMAGE_BASE_ROOT / args.client / args.plant / args.server
    camaras = sorted(p.stem for p in carpeta.glob("*.jpg"))
    if not camaras:
        print(f"No se encontraron bases en {carpeta}")
        return

    conn = db.get_connection()
    ventana = _VentanaRevisarBase()

    revisadas = marcadas = saltadas = 0
    try:
        for i, camara in enumerate(camaras, start=1):
            perfil = db.obtener_camara(conn, args.client, args.plant, args.server, camara)
            if perfil["estado_actual"] == "base_desactualizada":
                saltadas += 1
                continue

            ruta = base_path(args.client, args.plant, args.server, camara)
            titulo = f"{args.client}/{args.plant}/{args.server}/{camara}"
            accion = ventana.pedir_veredicto(titulo, ruta, i, len(camaras))
            revisadas += 1

            if accion == "desactualizada":
                db.marcar_base_desactualizada_manual(conn, args.client, args.plant, args.server, camara)
                db.crear_observacion(conn, perfil["id"], NOTA_DESACTUALIZADA)
                marcadas += 1
    finally:
        ventana.cerrar()
        conn.close()

    print(f"\nRevisadas: {revisadas} (marcadas como desactualizada: {marcadas})")
    print(f"Ya estaban desactualizadas, saltadas: {saltadas}")


if __name__ == "__main__":
    main()
