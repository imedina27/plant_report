"""Ventana para reemplazar bases marcadas como desactualizadas (ROADMAP.md, sección 2.8).

Separada del flujo diario a propósito: cuando la ventana de revisión marca una base como
desactualizada (botón "Base Desactualizada"), la imagen que disparó esa marca casi siempre tiene
un camión/montacargas en cuadro y no sirve para reemplazarla de una vez. Esta ventana deja que
alguien espere a que el camión se vaya, tome o busque una foto limpia, y la suba cuando le
convenga -- sin depender de que la corrida automática del día traiga una imagen útil.

Elegir un archivo no lo guarda de inmediato: se muestra junto a la base actual para confirmar que
se abrió la imagen correcta, y solo "Aceptar" la guarda como nueva base. Si no es la imagen
correcta, "Seleccionar imagen..." se puede volver a oprimir sin haber guardado nada todavía.

Fuente de la lista de pendientes: hoy escanea los marcadores `.desactualizada` en
IMAGE_BASE_ROOT (ver `image_compare.py`). El día que exista `perfil_camara` en la base de datos
(Fase 4), este es el único lugar que hay que cambiar para que la lista venga de ahí -- mismo
patrón que `umbral_para()`.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog

from image_compare import IMAGE_BASE_ROOT, limpiar_marcador_desactualizada, save_base
from ventana_revision import (
    ACENTO,
    DARK_THEME,
    FUENTE,
    LIGHT_THEME,
    OK,
    _cargar_para_tk,
    _oscurecer_titlebar,
    _tema_oscuro_del_sistema,
)

ANCHO_COLUMNA = 340
ALTO_COLUMNA = 220  # fijo -- si dependiera del tamaño de imagen, el layout saltaría según haya o no imagen


def _dialogo_info(parent: tk.Tk, theme: dict, oscuro: bool, titulo: str, mensaje: str) -> None:
    """Ventanita de aviso propia, en vez de messagebox.showinfo -- el messagebox nativo de
    Tkinter no sigue el tema oscuro/claro de la app (sale siempre con el look claro de Tk)."""
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


def _camaras_pendientes() -> list[tuple[str, str, str, str]]:
    pendientes = []
    for marcador in IMAGE_BASE_ROOT.glob("*/*/*/*.desactualizada"):
        cliente, planta, servidor = marcador.relative_to(IMAGE_BASE_ROOT).parts[:3]
        camara = marcador.stem
        pendientes.append((cliente, planta, servidor, camara))
    return sorted(pendientes)


class VentanaBases:
    def __init__(self) -> None:
        self._oscuro = _tema_oscuro_del_sistema()
        self.theme = DARK_THEME if self._oscuro else LIGHT_THEME
        t = self.theme

        self.root = tk.Tk()
        self.root.title("Bases desactualizadas — Quantum Labs")
        self.root.configure(bg=t["background"])
        self.root.geometry("1180x640")
        _oscurecer_titlebar(self.root, self._oscuro)

        self._img_base = None
        self._img_candidata = None
        self._ruta_candidata: Path | None = None
        self._pendientes: list[tuple[str, str, str, str]] = []

        self._construir_layout()
        self._refrescar_lista()

    def _construir_layout(self) -> None:
        t = self.theme
        tk.Label(self.root, text="Cámaras con base desactualizada", font=(FUENTE, 17, "bold"),
                 bg=t["background"], fg=t["text"]).pack(pady=(16, 10))

        cuerpo = tk.Frame(self.root, bg=t["background"])
        cuerpo.pack(fill="both", expand=True, padx=20, pady=(0, 16))

        panel_lista = tk.Frame(cuerpo, bg=t["background"])
        panel_lista.pack(side="left", fill="y", padx=(0, 16))

        self.lista = tk.Listbox(panel_lista, font=(FUENTE, 11), width=38, height=24,
                                 bg=t["frame_background"], fg=t["text"],
                                 selectbackground=ACENTO, selectforeground="white",
                                 highlightthickness=0, bd=0)
        self.lista.pack(fill="y")
        self.lista.bind("<<ListboxSelect>>", lambda _e: self._mostrar_preview())

        tk.Button(panel_lista, text="Actualizar lista", bg=t["frame_background"], fg=t["text"],
                  activebackground=t["border"], font=(FUENTE, 10), relief="flat", bd=0,
                  command=self._refrescar_lista).pack(fill="x", pady=(8, 0))

        panel_derecho = tk.Frame(cuerpo, bg=t["background"])
        panel_derecho.pack(side="left", fill="both", expand=True)

        self.label_camara = tk.Label(panel_derecho, text="Selecciona una cámara de la lista",
                                      font=(FUENTE, 12, "bold"), bg=t["background"], fg=t["text"],
                                      wraplength=700, justify="center")
        self.label_camara.pack(pady=(0, 10))

        frame_imgs = tk.Frame(panel_derecho, bg=t["background"])
        frame_imgs.pack()

        col_base = tk.Frame(frame_imgs, bg=t["frame_background"],
                             highlightbackground=t["border"], highlightthickness=1)
        col_base.grid(row=0, column=0, padx=6)
        tk.Label(col_base, text="Base actual (desactualizada)", font=(FUENTE, 11, "bold"),
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

        frame_botones = tk.Frame(panel_derecho, bg=t["background"])
        frame_botones.pack(pady=20)

        tk.Button(frame_botones, text="Seleccionar imagen...", bg=ACENTO, fg="white",
                  activebackground=ACENTO, font=(FUENTE, 11, "bold"), width=18, relief="flat", bd=0,
                  command=self._elegir_archivo).grid(row=0, column=0, padx=8)

        self.boton_aceptar = tk.Button(
            frame_botones, text="Aceptar", bg=OK, fg="white", activebackground=OK,
            font=(FUENTE, 11, "bold"), width=18, relief="flat", bd=0,
            command=self._confirmar_reemplazo, state="disabled",
        )
        self.boton_aceptar.grid(row=0, column=1, padx=8)

    def _refrescar_lista(self) -> None:
        self._pendientes = _camaras_pendientes()
        self.lista.delete(0, "end")
        for cliente, planta, servidor, camara in self._pendientes:
            self.lista.insert("end", f"{cliente}/{planta}/{servidor}/{camara}")
        self.label_camara.config(text=f"{len(self._pendientes)} cámara(s) pendiente(s) — selecciona una")
        self._limpiar_candidata()
        self.label_imagen_base.config(image="")
        self._img_base = None

    def _seleccion_actual(self) -> tuple[str, str, str, str] | None:
        seleccion = self.lista.curselection()
        if not seleccion:
            return None
        return self._pendientes[seleccion[0]]

    def _limpiar_candidata(self) -> None:
        t = self.theme
        self._ruta_candidata = None
        self._img_candidata = None
        self.label_imagen_candidata.config(image="", text="(ninguna todavía)", fg=t["tenue"])
        self.boton_aceptar.config(state="disabled")

    def _mostrar_preview(self) -> None:
        datos = self._seleccion_actual()
        if datos is None:
            return
        cliente, planta, servidor, camara = datos
        self.label_camara.config(text=f"{cliente}/{planta}/{servidor}/{camara}")
        self._limpiar_candidata()
        ruta_base = IMAGE_BASE_ROOT / cliente / planta / servidor / f"{camara}.jpg"
        if ruta_base.exists():
            self._img_base = _cargar_para_tk(ruta_base, ANCHO_COLUMNA)
            self.label_imagen_base.config(image=self._img_base)
        else:
            self.label_imagen_base.config(image="")

    def _elegir_archivo(self) -> None:
        datos = self._seleccion_actual()
        if datos is None:
            _dialogo_info(self.root, self.theme, self._oscuro,
                          "Bases desactualizadas", "Selecciona primero una cámara de la lista.")
            return
        cliente, planta, servidor, camara = datos
        elegido = filedialog.askopenfilename(
            title=f"Nueva base para {cliente}/{planta}/{servidor}/{camara}",
            filetypes=[("Imágenes JPG", "*.jpg *.jpeg")],
        )
        if not elegido:
            return
        self._ruta_candidata = Path(elegido)
        self._img_candidata = _cargar_para_tk(self._ruta_candidata, ANCHO_COLUMNA)
        self.label_imagen_candidata.config(image=self._img_candidata, text="")
        self.boton_aceptar.config(state="normal")

    def _confirmar_reemplazo(self) -> None:
        datos = self._seleccion_actual()
        if datos is None or self._ruta_candidata is None:
            return
        cliente, planta, servidor, camara = datos
        save_base(cliente, planta, servidor, camara, self._ruta_candidata)
        limpiar_marcador_desactualizada(cliente, planta, servidor, camara)
        self._refrescar_lista()
        _dialogo_info(
            self.root, self.theme, self._oscuro, "Base actualizada",
            f"La imagen base de la cámara {cliente}/{planta}/{servidor}/{camara} "
            "fue cambiada con éxito.",
        )

    def iniciar(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    VentanaBases().iniciar()
