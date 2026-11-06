"""Herramienta para reemplazar la base de imagen de cualquier cámara, fuera del flujo normal
(ROADMAP.md, 06/11/2026).

A diferencia de `ui/ventana_bases.py` (que solo lista cámaras ya marcadas `base_desactualizada`
dentro del flujo de `main.py`), aquí se puede elegir cualquier cámara del catálogo -- pensado para
cuando el cambio de base no sale de la revisión diaria, sino de una auditoría aparte (por ejemplo,
después de generar el reporte mensual y revisar varias cámaras a la vez).

Navegación tipo árbol (Cliente > Planta > Servidor > Cámara, igual que
`scripts/ventana_observaciones.py`), sin banderas de línea de comandos. Un punto azul marca las
cámaras que ya están en `base_desactualizada`, solo para ubicarlas rápido -- no es requisito para
poder cambiarles la base.

El reemplazo se confirma de inmediato por cámara, igual que `ui/ventana_bases.py` -- no hay un paso
de "Guardar todo al final": al dar Aceptar, la imagen elegida ya queda copiada como base, se
reinicia el historial/mediana, y la cámara vuelve a verde.

Uso: pipenv run python scripts/cambiar_base_camara.py
"""

from __future__ import annotations

import sys
import tkinter as tk
from datetime import date
from pathlib import Path
from tkinter import filedialog, ttk

sys.path.insert(0, str(Path(__file__).parent.parent))

from PIL import Image, ImageDraw, ImageTk

from comparacion.image_compare import (
    IMAGE_BASE_ROOT,
    guardar_historial_imagen,
    limpiar_base_mediana,
    limpiar_historial_imagen,
    save_base,
)
from persistencia import db
from ui.ventana_revision import (
    ACENTO,
    AZUL,
    DARK_THEME,
    FUENTE,
    LIGHT_THEME,
    OK,
    _cargar_para_tk,
    _oscurecer_titlebar,
    _tema_oscuro_del_sistema,
)

ANCHO_ARBOL = 280
ANCHO_COLUMNA = 340
ALTO_COLUMNA = 220  # fijo -- misma razón que en ui/ventana_bases.py: que el layout no salte


def _icono_punto(color: str | None) -> ImageTk.PhotoImage:
    """Punto azul (base desactualizada) o espacio transparente del mismo tamaño -- así la columna
    de texto del árbol no se mueve según haya o no punto."""
    img = Image.new("RGBA", (12, 12), (0, 0, 0, 0))
    if color:
        ImageDraw.Draw(img).ellipse((2, 2, 10, 10), fill=color)
    return ImageTk.PhotoImage(img)


def _dialogo_info(parent: tk.Tk, theme: dict, oscuro: bool, titulo: str, mensaje: str) -> None:
    """Igual que en `ui/ventana_bases.py` -- el messagebox nativo de Tkinter no sigue el tema
    oscuro/claro de la app."""
    t = theme
    ventana = tk.Toplevel(parent)
    ventana.title(titulo)
    ventana.configure(bg=t["background"])
    ventana.resizable(False, False)
    ventana.transient(parent)
    _oscurecer_titlebar(ventana, oscuro)

    tk.Label(ventana, text=mensaje, font=(FUENTE, 11), bg=t["background"], fg=t["text"],
             wraplength=360, justify="center").pack(padx=24, pady=(24, 14))
    tk.Button(ventana, text="Aceptar", bg=ACENTO, fg="white", activebackground=ACENTO,
              font=(FUENTE, 10, "bold"), width=12, relief="flat", bd=0,
              command=ventana.destroy).pack(pady=(0, 20))

    ventana.update_idletasks()
    x = parent.winfo_x() + (parent.winfo_width() - ventana.winfo_width()) // 2
    y = parent.winfo_y() + (parent.winfo_height() - ventana.winfo_height()) // 2
    ventana.geometry(f"+{x}+{y}")

    ventana.grab_set()
    ventana.wait_window()


class VentanaCambiarBase:
    def __init__(self) -> None:
        self._oscuro = _tema_oscuro_del_sistema()
        self.theme = DARK_THEME if self._oscuro else LIGHT_THEME
        t = self.theme

        self.root = tk.Tk()
        self.root.title("Cambiar Base de Cámaras — Quantum Labs")
        self.root.configure(bg=t["background"])
        self.root.geometry("1180x720")
        _oscurecer_titlebar(self.root, self._oscuro)
        self.root.protocol("WM_DELETE_WINDOW", self._cerrar)

        self._conn = db.get_connection()

        self._icono_desactualizada = _icono_punto(AZUL)
        self._icono_normal = _icono_punto(None)

        self._camara_por_item: dict[str, dict] = {}
        self._item_por_camara_id: dict[int, str] = {}
        self._camara_actual: dict | None = None
        self._img_base: ImageTk.PhotoImage | None = None
        self._img_candidata: ImageTk.PhotoImage | None = None
        self._ruta_candidata: Path | None = None

        self._construir_layout()
        self._cargar_arbol()

    # -- layout --------------------------------------------------------------

    def _construir_layout(self) -> None:
        t = self.theme
        tk.Label(self.root, text="Cambiar Base de Cámaras", font=(FUENTE, 17, "bold"),
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
            "CambiarBase.Treeview", background=t["frame_background"],
            fieldbackground=t["frame_background"], foreground=t["text"],
            font=(FUENTE, 10), borderwidth=0, rowheight=24,
        )
        style.map("CambiarBase.Treeview", background=[("selected", ACENTO)],
                  foreground=[("selected", "white")])

        self.arbol = ttk.Treeview(marco_arbol, style="CambiarBase.Treeview", show="tree",
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
        self.label_camara.pack(anchor="w", pady=(0, 14))

        frame_imgs = tk.Frame(contenido, bg=t["background"])
        frame_imgs.pack()

        col_base = tk.Frame(frame_imgs, bg=t["frame_background"],
                             highlightbackground=t["border"], highlightthickness=1)
        col_base.grid(row=0, column=0, padx=6)
        tk.Label(col_base, text="Base actual", font=(FUENTE, 11, "bold"),
                 bg=t["frame_background"], fg=t["text"]).pack(pady=(4, 2))
        visor_base = tk.Frame(col_base, bg=t["frame_background"], width=ANCHO_COLUMNA, height=ALTO_COLUMNA)
        visor_base.pack(padx=4, pady=(0, 4))
        visor_base.pack_propagate(False)
        self.label_imagen_base = tk.Label(visor_base, bg=t["frame_background"])
        self.label_imagen_base.pack(expand=True)

        col_candidata = tk.Frame(frame_imgs, bg=t["frame_background"],
                                  highlightbackground=t["border"], highlightthickness=1)
        col_candidata.grid(row=0, column=1, padx=6)
        tk.Label(col_candidata, text="Imagen seleccionada", font=(FUENTE, 11, "bold"),
                 bg=t["frame_background"], fg=t["text"]).pack(pady=(4, 2))
        visor_candidata = tk.Frame(col_candidata, bg=t["frame_background"],
                                    width=ANCHO_COLUMNA, height=ALTO_COLUMNA)
        visor_candidata.pack(padx=4, pady=(0, 4))
        visor_candidata.pack_propagate(False)
        self.label_imagen_candidata = tk.Label(
            visor_candidata, text="(ninguna todavía)", font=(FUENTE, 10),
            fg=t["tenue"], bg=t["frame_background"],
        )
        self.label_imagen_candidata.pack(expand=True)

        frame_botones = tk.Frame(contenido, bg=t["background"])
        frame_botones.pack(pady=20)

        self.boton_elegir = tk.Button(
            frame_botones, text="Seleccionar imagen...", bg=ACENTO, fg="white",
            activebackground=ACENTO, font=(FUENTE, 11, "bold"), width=18, relief="flat", bd=0,
            state="disabled", command=self._elegir_archivo,
        )
        self.boton_elegir.grid(row=0, column=0, padx=8)

        self.boton_aceptar = tk.Button(
            frame_botones, text="Aceptar", bg=OK, fg="white", activebackground=OK,
            font=(FUENTE, 11, "bold"), width=18, relief="flat", bd=0, state="disabled",
            command=self._confirmar_reemplazo,
        )
        self.boton_aceptar.grid(row=0, column=1, padx=8)

        tk.Button(frame_botones, text="Cerrar", bg=t["frame_background"], fg=t["text"],
                  activebackground=t["border"], font=(FUENTE, 11, "bold"), width=14, relief="flat", bd=0,
                  command=self._cerrar).grid(row=0, column=2, padx=8)

    # -- árbol cliente/planta/servidor/cámara --------------------------------

    def _cargar_arbol(self) -> None:
        camaras = db.listar_camaras(self._conn)
        desactualizadas = {
            (fila["cliente"], fila["planta"], fila["servidor"], fila["camara"])
            for fila in db.camaras_con_base_desactualizada(self._conn)
        }

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

            desactualizada = (cliente, planta, servidor, camara) in desactualizadas
            item = self.arbol.insert(
                nodo_servidor, "end", text=f"  {camara}",
                image=self._icono_desactualizada if desactualizada else self._icono_normal,
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
        self._cargar_camara(fila)

    def _cargar_camara(self, fila: dict) -> None:
        self._camara_actual = fila
        self._limpiar_candidata()
        self.label_camara.config(
            text=f"{fila['cliente']}/{fila['planta']}/{fila['servidor']}/{fila['camara']}"
        )
        ruta_base = IMAGE_BASE_ROOT / fila["cliente"] / fila["planta"] / fila["servidor"] / f"{fila['camara']}.jpg"
        if ruta_base.exists():
            self._img_base = _cargar_para_tk(ruta_base, ANCHO_COLUMNA)
            self.label_imagen_base.config(image=self._img_base)
        else:
            self._img_base = None
            self.label_imagen_base.config(image="")
        self.boton_elegir.config(state="normal")

    # -- reemplazo de base ----------------------------------------------------

    def _limpiar_candidata(self) -> None:
        t = self.theme
        self._ruta_candidata = None
        self._img_candidata = None
        self.label_imagen_candidata.config(image="", text="(ninguna todavía)", fg=t["tenue"])
        self.boton_aceptar.config(state="disabled")

    def _elegir_archivo(self) -> None:
        if self._camara_actual is None:
            return
        fila = self._camara_actual
        elegido = filedialog.askopenfilename(
            title=f"Nueva base para {fila['cliente']}/{fila['planta']}/{fila['servidor']}/{fila['camara']}",
            filetypes=[("Imágenes JPG", "*.jpg *.jpeg")],
        )
        if not elegido:
            return
        self._ruta_candidata = Path(elegido)
        self._img_candidata = _cargar_para_tk(self._ruta_candidata, ANCHO_COLUMNA)
        self.label_imagen_candidata.config(image=self._img_candidata, text="")
        self.boton_aceptar.config(state="normal")

    def _confirmar_reemplazo(self) -> None:
        if self._camara_actual is None or self._ruta_candidata is None:
            return
        fila = self._camara_actual
        cliente, planta, servidor, camara = fila["cliente"], fila["planta"], fila["servidor"], fila["camara"]

        save_base(cliente, planta, servidor, camara, self._ruta_candidata)
        # Igual que ui/ventana_bases.py: borra mediana e historial viejos -- si no, la comparación
        # seguiría midiendo contra fotos de antes del reemplazo (ver ROADMAP.md, 27/10/2026).
        limpiar_base_mediana(cliente, planta, servidor, camara)
        limpiar_historial_imagen(cliente, planta, servidor, camara)
        guardar_historial_imagen(cliente, planta, servidor, camara, self._ruta_candidata, date.today())
        db.marcar_base_reemplazada(self._conn, cliente, planta, servidor, camara)

        self._actualizar_icono_arbol(fila["id"])
        self._cargar_camara(fila)  # refresca "Base actual" con la imagen recién copiada
        _dialogo_info(
            self.root, self.theme, self._oscuro, "Base actualizada",
            f"La imagen base de la cámara {cliente}/{planta}/{servidor}/{camara} "
            "fue cambiada con éxito.",
        )

    def _actualizar_icono_arbol(self, camara_id: int) -> None:
        item = self._item_por_camara_id.get(camara_id)
        if item is not None:
            self.arbol.item(item, image=self._icono_normal)

    def _cerrar(self) -> None:
        self._conn.close()
        self.root.destroy()

    def iniciar(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    VentanaCambiarBase().iniciar()
