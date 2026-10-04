"""Ventana de revisión humana para Fase 2 (ROADMAP.md, secciones 2.3 y 2.7).

Una sola ventana persistente, abierta desde que arranca la corrida hasta que
termina. Normalmente muestra progreso ("procesando cámara X de Y"); cuando una
cámara da REVISAR, el mismo panel cambia a mostrar la comparación (base vs.
actual + diagnóstico + 3 botones) y bloquea ahí hasta que se resuelve, luego
vuelve a mostrar progreso y sigue sola.

Construida con Tkinter (incluido en Python) + Pillow (única dependencia nueva,
para que Tkinter pueda mostrar JPG). Un solo hilo: el bucle por cámara llama a
`mostrar_procesando()` entre cámara y cámara (no bloquea), y a
`pedir_revision()` solo cuando hace falta (ahí sí bloquea, vía
`wait_variable`, hasta que se elige un botón).

Paleta y tipografía: tomadas de `styles/stylesheet.py` y `Images/logos/` del
proyecto hermano `Cam_Lens_V2` (PyQt, mismo cliente — Quantum Labs), copiadas
a este repo (`assets/`) para no depender de esa ruta. Tema oscuro/claro
automático según el tema del sistema operativo (sin botón para cambiarlo, a
petición explícita) -- se lee una sola vez al abrir la ventana.

Las imágenes se muestran con una cuadrícula delgada superpuesta (ancho
dividido en 10, alto en partes del mismo tamaño que resulten -- celdas
cuadradas, no 10x10 forzado) para ayudar a juzgar a ojo si la cámara se movió.
La cuadrícula se dibuja sobre la copia en memoria que se muestra en pantalla
nada más -- nunca toca el .jpg original guardado en disco.
"""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path

from PIL import Image, ImageDraw, ImageTk

ASSETS_DIR = Path(__file__).parent / "assets"

# --- Paleta Quantum Labs (de styles/stylesheet.py) ------------------------
FUENTE = "Segoe UI"

LIGHT_THEME = {
    "background": "#FAF8F6",
    "text": "#1E1E28",
    "frame_background": "#EDE8E2",
    "border": "#DCD4C9",
    "tenue": "#8C8C94",
}
DARK_THEME = {
    "background": "#1E1E28",
    "text": "#F5F5FA",
    "frame_background": "#3C3C46",
    "border": "#50505A",
    "tenue": "#8C8C94",
}

# Colores de estado -- iguales en los dos temas (igual que en stylesheet.py)
ACENTO = "#E2724B"  # tambien el color del logo
OK = "#2FA36B"
WARN = "#E0902E"
FAIL = "#D9534F"
AZUL = "#3B7DDD"

MAX_ANCHO_PANEL = 560
MAX_ANCHO_LOGO = 150

DIVISIONES_CUADRICULA = 10
COLOR_CUADRICULA = (255, 255, 255, 110)  # blanco semitransparente, visible en casi cualquier escena


def _oscurecer_titlebar(root: tk.Tk, oscuro: bool) -> None:
    """La barra de titulo la pinta Windows (DWM), no Tkinter -- por defecto
    sale blanca aunque el contenido de la ventana este en modo oscuro. Hay
    que pedirselo explicitamente via DwmSetWindowAttribute. Si falla (SO
    distinto, Windows viejo sin esta API), se ignora -- la ventana sigue
    funcionando, solo con la barra de titulo por defecto."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        valor = ctypes.c_int(1 if oscuro else 0)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(valor), ctypes.sizeof(valor)
        )
    except (AttributeError, OSError):
        pass


def _tema_oscuro_del_sistema() -> bool:
    """Lee el tema de Windows (Configuración > Personalización > Colores).
    Si no se puede leer (otro SO, registro bloqueado), asume claro."""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        clave = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        valor, _ = winreg.QueryValueEx(clave, "AppsUseLightTheme")
        return valor == 0  # 0 = oscuro, 1 = claro
    except OSError:
        return False


def _con_cuadricula(img: Image.Image) -> Image.Image:
    """Agrega lineas guia delgadas sin tocar la imagen original (opera sobre
    una copia). Celdas cuadradas: el ancho se divide en 10, y el alto usa el
    mismo tamaño de celda (no un 10x10 forzado que deformaria la proporcion)."""
    base = img.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    paso = base.width / DIVISIONES_CUADRICULA
    x = paso
    while x < base.width:
        draw.line([(x, 0), (x, base.height)], fill=COLOR_CUADRICULA, width=1)
        x += paso
    y = paso
    while y < base.height:
        draw.line([(0, y), (base.width, y)], fill=COLOR_CUADRICULA, width=1)
        y += paso

    return Image.alpha_composite(base, overlay).convert("RGB")


def _cargar_para_tk(path: Path, max_ancho: int, con_cuadricula: bool = False) -> ImageTk.PhotoImage:
    img = Image.open(path)
    ratio = max_ancho / img.width
    img = img.resize((max_ancho, int(img.height * ratio)), Image.LANCZOS)
    if con_cuadricula:
        img = _con_cuadricula(img)
    return ImageTk.PhotoImage(img)


class VentanaRevision:
    def __init__(self, titulo_app: str = "Revisión de Cámaras"):
        oscuro = _tema_oscuro_del_sistema()
        self.theme = DARK_THEME if oscuro else LIGHT_THEME
        t = self.theme

        self.root = tk.Tk()
        self.root.title(f"{titulo_app} — Quantum Labs")
        self.root.configure(bg=t["background"])
        self.root.geometry("1280x760")
        _oscurecer_titlebar(self.root, oscuro)

        self._accion = tk.StringVar(value="")
        self._imgs_referencia = []  # evita que Tkinter las recolecte como basura

        self._construir_header(titulo_app)
        self.contenido = tk.Frame(self.root, bg=t["background"])
        self.contenido.pack(fill="both", expand=True, padx=20, pady=10)
        self._construir_footer()

        self._mostrar_frame_procesando()

    # -- estructura fija (header/footer) ------------------------------------

    def _construir_header(self, titulo_app: str) -> None:
        t = self.theme
        header = tk.Frame(self.root, bg=t["background"])
        header.pack(fill="x", padx=20, pady=(16, 6))

        logo_path = ASSETS_DIR / "QuantumLab-Logo-01.png"
        if logo_path.exists():
            self._logo_img = _cargar_para_tk(logo_path, MAX_ANCHO_LOGO)
            tk.Label(header, image=self._logo_img, bg=t["background"]).pack(side="left", padx=(0, 16))

        tk.Label(header, text=titulo_app, font=(FUENTE, 22, "bold"),
                 bg=t["background"], fg=t["text"]).pack(side="left")

        tk.Frame(self.root, bg=t["border"], height=2).pack(fill="x", padx=20)

    def _construir_footer(self) -> None:
        """"Barra de progreso": aqui se construye a mano con Frames en vez de
        ttk.Progressbar -- en Windows, ttk a veces ignora los colores
        personalizados y dibuja con el tema nativo (tira clara casi invisible
        sobre fondo oscuro, visto en pantalla). Con Frames el color y el alto
        quedan bajo control total, sin depender del tema nativo."""
        t = self.theme
        footer = tk.Frame(self.root, bg=t["background"])
        footer.pack(fill="x", padx=20, pady=(0, 20))

        fila_textos = tk.Frame(footer, bg=t["background"])
        fila_textos.pack(fill="x")
        self.label_conteo = tk.Label(fila_textos, text="", font=(FUENTE, 11, "bold"),
                                      bg=t["background"], fg=t["text"])
        self.label_conteo.pack(side="left")
        self.label_porcentaje = tk.Label(fila_textos, text="", font=(FUENTE, 11),
                                          bg=t["background"], fg=t["tenue"])
        self.label_porcentaje.pack(side="right")

        ALTO_BARRA = 20
        self._barra_fondo = tk.Frame(footer, bg=t["frame_background"], height=ALTO_BARRA)
        self._barra_fondo.pack(fill="x", pady=(6, 0))
        self._barra_fondo.pack_propagate(False)
        self._barra_relleno = tk.Frame(self._barra_fondo, bg=ACENTO, width=0)
        self._barra_relleno.place(x=0, y=0, relheight=1, width=0)

    def _actualizar_barra(self, indice: int, total: int) -> None:
        fraccion = (indice / total) if total else 0
        self._barra_fondo.update_idletasks()
        ancho_total = self._barra_fondo.winfo_width()
        self._barra_relleno.place(width=max(0, int(ancho_total * fraccion)))

    def _limpiar_contenido(self) -> None:
        for widget in self.contenido.winfo_children():
            widget.destroy()

    # -- estado 1: procesando (no bloquea) ----------------------------------

    def mostrar_procesando(self, camara_actual: str, indice: int, total: int) -> None:
        t = self.theme
        self._limpiar_contenido()
        frame = tk.Frame(self.contenido, bg=t["background"])
        frame.pack(expand=True)
        tk.Label(frame, text="Procesando…", font=(FUENTE, 16, "bold"),
                 bg=t["background"], fg=t["text"]).pack(pady=(40, 8))
        tk.Label(frame, text=camara_actual, font=(FUENTE, 12),
                 bg=t["background"], fg=t["tenue"]).pack()

        porcentaje = round(indice / total * 100) if total else 0
        self.label_conteo.config(text=f"{indice} de {total} cámaras")
        self.label_porcentaje.config(text=f"{porcentaje}%")
        self._actualizar_barra(indice, total)

        self.root.update()

    # -- estado 2: revisar (bloquea hasta elegir un boton) ------------------

    def pedir_revision(self, titulo: str, diagnostico: str,
                        ruta_base: Path, ruta_actual: Path) -> str:
        t = self.theme
        self._limpiar_contenido()
        self._imgs_referencia.clear()

        tk.Label(self.contenido, text=titulo, font=(FUENTE, 17, "bold"),
                 bg=t["background"], fg=t["text"]).pack(pady=(4, 2))
        tk.Label(self.contenido, text=diagnostico, font=(FUENTE, 10), fg=t["tenue"],
                 bg=t["background"], justify="center").pack(pady=(0, 10))

        frame_imgs = tk.Frame(self.contenido, bg=t["background"])
        frame_imgs.pack()

        img_base = _cargar_para_tk(ruta_base, MAX_ANCHO_PANEL, con_cuadricula=True)
        img_actual = _cargar_para_tk(ruta_actual, MAX_ANCHO_PANEL, con_cuadricula=True)
        self._imgs_referencia.extend([img_base, img_actual])

        col_base = tk.Frame(frame_imgs, bg=t["frame_background"],
                             highlightbackground=t["border"], highlightthickness=1)
        col_base.grid(row=0, column=0, padx=6)
        tk.Label(col_base, text="Base", font=(FUENTE, 11, "bold"),
                 bg=t["frame_background"], fg=t["text"]).pack(pady=(4, 2))
        tk.Label(col_base, image=img_base, bg=t["frame_background"]).pack(padx=4, pady=(0, 4))

        col_actual = tk.Frame(frame_imgs, bg=t["frame_background"],
                               highlightbackground=t["border"], highlightthickness=1)
        col_actual.grid(row=0, column=1, padx=6)
        tk.Label(col_actual, text="Actual", font=(FUENTE, 11, "bold"),
                 bg=t["frame_background"], fg=t["text"]).pack(pady=(4, 2))
        tk.Label(col_actual, image=img_actual, bg=t["frame_background"]).pack(padx=4, pady=(0, 4))

        frame_botones = tk.Frame(self.contenido, bg=t["background"])
        frame_botones.pack(pady=16)

        self._accion.set("")
        tk.Button(frame_botones, text="Bien", bg=OK, fg="white", activebackground=OK,
                  font=(FUENTE, 11, "bold"), width=14, relief="flat", bd=0,
                  command=lambda: self._accion.set("bien")).grid(row=0, column=0, padx=8)
        tk.Button(frame_botones, text="Mal", bg=FAIL, fg="white", activebackground=FAIL,
                  font=(FUENTE, 11, "bold"), width=14, relief="flat", bd=0,
                  command=lambda: self._accion.set("mal")).grid(row=0, column=1, padx=8)
        tk.Button(frame_botones, text="Base Desactualizada", bg=AZUL, fg="white", activebackground=AZUL,
                  font=(FUENTE, 11, "bold"), width=18, relief="flat", bd=0,
                  command=lambda: self._accion.set("desactualizada")).grid(row=0, column=2, padx=8)

        self.root.wait_variable(self._accion)
        return self._accion.get()

    def _mostrar_frame_procesando(self) -> None:
        self.mostrar_procesando("esperando…", 0, 1)

    def cerrar(self) -> None:
        self.root.destroy()


if __name__ == "__main__":
    import time

    from image_compare import base_path, compare_camera_image

    camaras_demo = [
        "AbInBev/ZACATECAS/QLYMSPROD01/A1p",
        "AbInBev/ZACATECAS/QLYMSPROD01/A1t1",
        "AbInBev/ZACATECAS/QLYMSPROD01/A2t1",
        "AbInBev/MEDELLIN/QLYMSPROD04/EP1",
        "AbInBev/MEDELLIN/QLYMSPROD04/P3E",
        "AbInBev/ZACATECAS/QLYMSPROD01/A3p",  # esta es la que da REVISAR
        "AbInBev/ZACATECAS/QLYMSPROD01/A3t1",
        "AbInBev/ZACATECAS/QLYMSPROD01/A3t2",
    ]

    ventana = VentanaRevision()
    total = len(camaras_demo)

    for i, camara_id in enumerate(camaras_demo, start=1):
        ventana.mostrar_procesando(camara_id, i - 1, total)
        time.sleep(0.5)

        if camara_id.endswith("A3p"):
            cliente, planta, servidor, camara = "AbInBev", "ZACATECAS", "QLYMSPROD01", "A3p"
            ruta_actual = Path("Test/Check Plants/AbInBev/09- Septiembre/300926/ZACATECAS/QLYMSPROD01/A3p.jpg")
            ruta_base = base_path(cliente, planta, servidor, camara)
            r = compare_camera_image(ruta_actual, cliente, planta, servidor, camara)
            diagnostico = (
                f"Estado: {r['status']}  —  {r['motivo']}\n"
                f"ORB: {r['orb_inliers']} inliers, {r['orb_desp']:.1f} px      "
                f"Correlación de fase: confianza {r['fase_conf']:.2f}, {r['fase_desp']:.1f} px"
            )
            accion = ventana.pedir_revision(camara_id, diagnostico, ruta_base, ruta_actual)
            print(f"{camara_id}: acción elegida = {accion}")

    ventana.mostrar_procesando("Corrida completa", total, total)
    time.sleep(1.5)
    ventana.cerrar()
