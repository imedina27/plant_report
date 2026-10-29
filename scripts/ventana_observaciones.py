"""Herramienta temporal para administrar la bitácora de observaciones (`observacion_camara`) de
cualquier cámara -- ROADMAP.md, 29/10/2026.

Es temporal a propósito: la edición libre de cámaras/observaciones está pensada para vivir en un
programa de administración aparte (fuera de este repo); mientras ese programa no exista, esta
ventana cubre el hueco real de hoy -- no hay forma de solucionar una observación, ni de agregar una
nueva a una cámara que no esté pasando ahora mismo por `ventana_revision.py`.

Navegación tipo árbol (Cliente > Planta > Servidor > Cámara, expandible/colapsable con
`ttk.Treeview`). Cada cámara con al menos una observación vigente hoy (activa, o resuelta hace 15
días o menos -- mismo criterio que usa el PDF) se marca con un punto verde, para no tener que entrar
cámara por cámara a buscar cuál tiene algo pendiente.

Los cambios sobre una cámara (solucionar observaciones, escribir una nueva) quedan solo en memoria
hasta Aceptar o Guardar -- cambiar de cámara con cambios sin guardar pide confirmación antes de
descartarlos; Cancelar sí cierra de inmediato sin preguntar (decisión explícita del usuario,
29/10/2026).

Uso: pipenv run python scripts/ventana_observaciones.py
"""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk

sys.path.insert(0, str(Path(__file__).parent.parent))

from PIL import Image, ImageDraw, ImageTk

from persistencia import db
from reporte.datos_reporte import DIAS_OBSERVACION_RESUELTA_VISIBLE
from ui.ventana_revision import (
    ACENTO,
    DARK_THEME,
    FAIL,
    FUENTE,
    LIGHT_THEME,
    OK,
    _oscurecer_titlebar,
    _tema_oscuro_del_sistema,
)

ANCHO_ARBOL = 280


def _icono_punto(color: str | None) -> ImageTk.PhotoImage:
    """Punto verde (tiene observación vigente) o espacio transparente del mismo tamaño (no tiene) --
    así la columna de texto del árbol no se mueve según haya o no punto."""
    img = Image.new("RGBA", (12, 12), (0, 0, 0, 0))
    if color:
        ImageDraw.Draw(img).ellipse((2, 2, 10, 10), fill=color)
    return ImageTk.PhotoImage(img)


def _dialogo_confirmar(root: tk.Tk, theme: dict, oscuro: bool, mensaje: str) -> bool:
    """Ventana modal Aceptar/Cancelar -- regresa `True` si se eligió Aceptar (descartar)."""
    t = theme
    resultado = tk.BooleanVar(value=False)
    ventana = tk.Toplevel(root)
    ventana.title("Cambios sin guardar")
    ventana.configure(bg=t["background"])
    ventana.resizable(False, False)
    ventana.transient(root)
    _oscurecer_titlebar(ventana, oscuro)

    tk.Label(ventana, text=mensaje, font=(FUENTE, 11), bg=t["background"], fg=t["text"],
             wraplength=360, justify="center").pack(padx=24, pady=(24, 14))

    frame_botones = tk.Frame(ventana, bg=t["background"])
    frame_botones.pack(pady=(0, 20))

    def _elegir(valor: bool) -> None:
        resultado.set(valor)
        ventana.destroy()

    tk.Button(frame_botones, text="Aceptar", bg=FAIL, fg="white", activebackground=FAIL,
              font=(FUENTE, 10, "bold"), width=12, relief="flat", bd=0,
              command=lambda: _elegir(True)).pack(side="left", padx=6)
    tk.Button(frame_botones, text="Cancelar", bg=t["frame_background"], fg=t["text"],
              activebackground=t["border"], font=(FUENTE, 10, "bold"), width=12, relief="flat", bd=0,
              command=lambda: _elegir(False)).pack(side="left", padx=6)

    ventana.update_idletasks()
    x = root.winfo_x() + (root.winfo_width() - ventana.winfo_width()) // 2
    y = root.winfo_y() + (root.winfo_height() - ventana.winfo_height()) // 2
    ventana.geometry(f"+{x}+{y}")

    ventana.grab_set()
    ventana.wait_window()
    return resultado.get()


class VentanaObservaciones:
    def __init__(self) -> None:
        self._oscuro = _tema_oscuro_del_sistema()
        self.theme = DARK_THEME if self._oscuro else LIGHT_THEME
        t = self.theme

        self.root = tk.Tk()
        self.root.title("Observaciones de Cámaras — Quantum Labs")
        self.root.configure(bg=t["background"])
        self.root.geometry("1300x760")
        _oscurecer_titlebar(self.root, self._oscuro)
        self.root.protocol("WM_DELETE_WINDOW", self._cerrar)

        self._conn = db.get_connection()

        self._icono_con_obs = _icono_punto("#2FA36B")
        self._icono_sin_obs = _icono_punto(None)

        self._camara_por_item: dict[str, dict] = {}
        self._item_por_camara_id: dict[int, str] = {}
        self._prev_selection_iid: str | None = None
        self._camara_actual: dict | None = None
        self._observaciones_actuales: list[dict] = []
        self._pending_resueltas: set[int] = set()

        self._construir_layout()
        self._cargar_arbol()

    # -- layout --------------------------------------------------------------

    def _construir_layout(self) -> None:
        t = self.theme
        tk.Label(self.root, text="Observaciones de Cámaras", font=(FUENTE, 17, "bold"),
                 bg=t["background"], fg=t["text"]).pack(pady=(16, 10))

        cuerpo = tk.Frame(self.root, bg=t["background"])
        cuerpo.pack(fill="both", expand=True, padx=20, pady=(0, 16))

        panel_arbol = tk.Frame(cuerpo, bg=t["background"])
        panel_arbol.pack(side="left", fill="y", padx=(0, 20))
        tk.Label(panel_arbol, text="Cliente / Planta / Servidor / Cámara", font=(FUENTE, 10, "bold"),
                 bg=t["background"], fg=t["tenue"]).pack(anchor="w")

        marco_arbol = tk.Frame(panel_arbol, bg=t["background"],
                                highlightbackground=t["border"], highlightthickness=1)
        marco_arbol.pack(fill="y", expand=True)
        scrollbar = tk.Scrollbar(marco_arbol)
        scrollbar.pack(side="right", fill="y")

        style = ttk.Style(self.root)
        style.theme_use("default")
        style.configure(
            "Observaciones.Treeview", background=t["frame_background"],
            fieldbackground=t["frame_background"], foreground=t["text"],
            font=(FUENTE, 10), borderwidth=0, rowheight=24,
        )
        style.map("Observaciones.Treeview", background=[("selected", ACENTO)],
                  foreground=[("selected", "white")])

        self.arbol = ttk.Treeview(marco_arbol, style="Observaciones.Treeview", show="tree",
                                   height=30, yscrollcommand=scrollbar.set)
        self.arbol.pack(side="left", fill="y")
        self.arbol.column("#0", width=ANCHO_ARBOL)
        scrollbar.config(command=self.arbol.yview)
        self.arbol.bind("<<TreeviewSelect>>", self._on_tree_select)

        panel_derecho = tk.Frame(cuerpo, bg=t["background"], highlightbackground=t["border"],
                                  highlightthickness=1)
        panel_derecho.pack(side="left", fill="both", expand=True)
        contenido = tk.Frame(panel_derecho, bg=t["background"])
        contenido.pack(fill="both", expand=True, padx=14, pady=14)

        self.label_camara = tk.Label(contenido, text="Selecciona una cámara",
                                      font=(FUENTE, 13, "bold"), bg=t["background"], fg=t["text"])
        self.label_camara.pack(anchor="w", pady=(0, 10))

        tk.Label(contenido, text="Observaciones", font=(FUENTE, 10, "bold"),
                 bg=t["background"], fg=t["tenue"]).pack(anchor="w")
        marco_obs = tk.Frame(contenido, bg=t["frame_background"],
                              highlightbackground=t["border"], highlightthickness=1)
        marco_obs.pack(fill="x", pady=(4, 16))
        self.frame_observaciones = tk.Frame(marco_obs, bg=t["background"])
        self.frame_observaciones.pack(fill="x", padx=10, pady=10)

        tk.Label(contenido, text="Nueva observación", font=(FUENTE, 10, "bold"),
                 bg=t["background"], fg=t["tenue"]).pack(anchor="w")
        self._texto_nueva = tk.Text(
            contenido, height=4, font=(FUENTE, 10), wrap="word",
            bg=t["frame_background"], fg=t["text"], insertbackground=t["text"],
            relief="flat", highlightbackground=t["border"], highlightthickness=1,
        )
        self._texto_nueva.pack(fill="x", pady=(4, 20))

        frame_botones = tk.Frame(contenido, bg=t["background"])
        frame_botones.pack(anchor="w")

        self.boton_aceptar = tk.Button(
            frame_botones, text="Aceptar", bg=OK, fg="white", activebackground=OK,
            font=(FUENTE, 11, "bold"), width=14, relief="flat", bd=0, state="disabled",
            command=lambda: self._guardar(cerrar=True),
        )
        self.boton_aceptar.grid(row=0, column=0, padx=(0, 8))

        self.boton_guardar = tk.Button(
            frame_botones, text="Guardar", bg=ACENTO, fg="white", activebackground=ACENTO,
            font=(FUENTE, 11, "bold"), width=14, relief="flat", bd=0, state="disabled",
            command=lambda: self._guardar(cerrar=False),
        )
        self.boton_guardar.grid(row=0, column=1, padx=8)

        self.boton_cancelar = tk.Button(
            frame_botones, text="Cancelar", bg=t["frame_background"], fg=t["text"],
            activebackground=t["border"], font=(FUENTE, 11, "bold"), width=14, relief="flat", bd=0,
            command=self._cerrar,
        )
        self.boton_cancelar.grid(row=0, column=2, padx=8)

        self._refrescar_observaciones_ui()

    # -- árbol cliente/planta/servidor/cámara --------------------------------

    def _cargar_arbol(self) -> None:
        camaras = db.listar_camaras(self._conn)
        con_observacion = db.camaras_con_observaciones_vigentes(
            self._conn, DIAS_OBSERVACION_RESUELTA_VISIBLE
        )

        nodos_cliente: dict[str, str] = {}
        nodos_planta: dict[tuple[str, str], str] = {}
        nodos_servidor: dict[tuple[str, str, str], str] = {}

        for fila in camaras:
            cliente, planta, servidor, camara = fila["cliente"], fila["planta"], fila["servidor"], fila["camara"]

            nodo_cliente = nodos_cliente.get(cliente)
            if nodo_cliente is None:
                nodo_cliente = self.arbol.insert("", "end", text=cliente)
                nodos_cliente[cliente] = nodo_cliente

            nodo_planta = nodos_planta.get((cliente, planta))
            if nodo_planta is None:
                nodo_planta = self.arbol.insert(nodo_cliente, "end", text=planta)
                nodos_planta[(cliente, planta)] = nodo_planta

            nodo_servidor = nodos_servidor.get((cliente, planta, servidor))
            if nodo_servidor is None:
                nodo_servidor = self.arbol.insert(nodo_planta, "end", text=servidor)
                nodos_servidor[(cliente, planta, servidor)] = nodo_servidor

            tiene_obs = fila["id"] in con_observacion
            item = self.arbol.insert(
                nodo_servidor, "end", text=f"  {camara}",
                image=self._icono_con_obs if tiene_obs else self._icono_sin_obs,
            )
            self._camara_por_item[item] = fila
            self._item_por_camara_id[fila["id"]] = item

    def _on_tree_select(self, _event=None) -> None:
        seleccion = self.arbol.selection()
        if not seleccion:
            return
        iid = seleccion[0]
        fila = self._camara_por_item.get(iid)
        if fila is None:
            return  # nodo cliente/planta/servidor -- no afecta el panel derecho

        if self._camara_actual is not None and self._camara_actual["id"] == fila["id"]:
            return

        if self._hay_cambios_sin_guardar() and not _dialogo_confirmar(
            self.root, self.theme, self._oscuro,
            "Hay cambios sin guardar en esta cámara. ¿Deseas descartarlos?",
        ):
            if self._prev_selection_iid is not None:
                self.arbol.selection_set(self._prev_selection_iid)
            else:
                self.arbol.selection_remove(iid)
            return

        self._prev_selection_iid = iid
        self._cargar_camara(fila)

    def _cargar_camara(self, fila: dict) -> None:
        self._camara_actual = fila
        self._pending_resueltas = set()
        self._observaciones_actuales = db.observaciones_vigentes_de_camara(
            self._conn, fila["id"], DIAS_OBSERVACION_RESUELTA_VISIBLE
        )
        self.label_camara.config(
            text=f"{fila['cliente']}/{fila['planta']}/{fila['servidor']}/{fila['camara']}"
        )
        self._texto_nueva.delete("1.0", "end")
        self._refrescar_observaciones_ui()
        self.boton_aceptar.config(state="normal")
        self.boton_guardar.config(state="normal")

    # -- observaciones de la cámara seleccionada -----------------------------

    def _hay_cambios_sin_guardar(self) -> bool:
        if self._camara_actual is None:
            return False
        texto = self._texto_nueva.get("1.0", "end-1c").strip()
        return bool(self._pending_resueltas) or bool(texto)

    def _refrescar_observaciones_ui(self) -> None:
        t = self.theme
        for widget in self.frame_observaciones.winfo_children():
            widget.destroy()
        if not self._observaciones_actuales:
            tk.Label(self.frame_observaciones, text="Sin observaciones vigentes", font=(FUENTE, 10),
                     fg=t["tenue"], bg=t["background"]).pack(anchor="w", pady=4)
            return
        for obs in self._observaciones_actuales:
            ya_resuelta = obs["resuelta"]
            pendiente = obs["id"] in self._pending_resueltas
            tachado = ya_resuelta or pendiente

            fila = tk.Frame(self.frame_observaciones, bg=t["background"])
            fila.pack(fill="x", pady=3)
            tk.Label(
                fila, text=f"{obs['creado_en']:%d/%m/%Y}: {obs['texto']}",
                font=(FUENTE, 10, "overstrike") if tachado else (FUENTE, 10),
                fg=t["tenue"] if tachado else t["text"], bg=t["background"],
                wraplength=460, justify="left", anchor="w",
            ).pack(side="left", fill="x", expand=True)

            # Ya resuelta en la BD: botón "Solucionar" deshabilitado, no "Deshacer" -- eso es solo
            # para un cambio marcado en esta sesión que todavía no se guarda (pedido 29/10/2026).
            if ya_resuelta:
                texto_boton, color_boton, color_texto, estado = "Solucionar", t["frame_background"], t["tenue"], "disabled"
            elif pendiente:
                texto_boton, color_boton, color_texto, estado = "Deshacer", t["frame_background"], t["text"], "normal"
            else:
                texto_boton, color_boton, color_texto, estado = "Solucionar", ACENTO, "white", "normal"

            tk.Button(
                fila, text=texto_boton, bg=color_boton, fg=color_texto, activebackground=color_boton,
                font=(FUENTE, 9, "bold"), relief="flat", bd=0, width=10, state=estado,
                command=(lambda oid=obs["id"]: self._alternar_solucionar(oid)) if not ya_resuelta else None,
            ).pack(side="right", padx=(8, 0))

    def _alternar_solucionar(self, observacion_id: int) -> None:
        if observacion_id in self._pending_resueltas:
            self._pending_resueltas.discard(observacion_id)
        else:
            self._pending_resueltas.add(observacion_id)
        self._refrescar_observaciones_ui()

    # -- guardar/cancelar -----------------------------------------------------

    def _guardar(self, cerrar: bool) -> None:
        if self._camara_actual is None:
            return
        for observacion_id in self._pending_resueltas:
            db.marcar_observacion_resuelta(self._conn, observacion_id)
        texto = self._texto_nueva.get("1.0", "end-1c").strip()
        if texto:
            db.crear_observacion(self._conn, self._camara_actual["id"], texto)

        self._actualizar_punto_arbol(self._camara_actual["id"])

        if cerrar:
            self._cerrar()
            return

        self._pending_resueltas = set()
        self._texto_nueva.delete("1.0", "end")
        self._observaciones_actuales = db.observaciones_vigentes_de_camara(
            self._conn, self._camara_actual["id"], DIAS_OBSERVACION_RESUELTA_VISIBLE
        )
        self._refrescar_observaciones_ui()

    def _actualizar_punto_arbol(self, camara_id: int) -> None:
        item = self._item_por_camara_id.get(camara_id)
        if item is None:
            return
        tiene_obs = db.camara_tiene_observacion_vigente(
            self._conn, camara_id, DIAS_OBSERVACION_RESUELTA_VISIBLE
        )
        self.arbol.item(item, image=self._icono_con_obs if tiene_obs else self._icono_sin_obs)

    def _cerrar(self) -> None:
        self._conn.close()
        self.root.destroy()

    def iniciar(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    VentanaObservaciones().iniciar()
