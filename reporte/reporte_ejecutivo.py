"""Reporte ejecutivo (Fase 4, ROADMAP.md): un PDF por cliente, con el resumen de todos sus
servidores (temperatura CPU/GPU, uso de disco, conteo de cámaras) y el detalle de las cámaras con
falla, por servidor.

Estilo visual (paleta, encabezado/pie, Tables de ReportLab con banda oscura + franjas alternadas)
adaptado de `models/reporte_pdf.py` en el proyecto hermano `Cam_Lens_V2` -- mismo cliente (Quantum
Labs), mismo logo (`assets/QuantumLab-Logo-01.png`, ya copiado a este repo). No se modificó ni se
importó nada de ese proyecto; solo se replicó el patrón visual porque el contenido es distinto (una
ficha de instalación de una sola cámara allá, un resumen diario multi-servidor aquí).

Módulo puro: recibe los datos ya resueltos (`ResumenServidor`), no sabe nada de la base de datos ni
de la API de Monit_Servers_V2 -- eso lo arma el llamador (`main.py` + `monit_client.py`). Así se
puede generar un PDF de prueba con datos inventados sin tocar ninguna base de datos real (ver
`scripts/mock_reporte_ejecutivo.py`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from io import BytesIO
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from ui.ventana_revision import _abrir_imagen_segura, _con_cuadricula

LOGO = Path(__file__).parent.parent / "assets" / "QuantumLab-Logo-01.png"

MARGEN_PT = 24
ANCHO_CONTENIDO_PT = letter[0] - 2 * MARGEN_PT
_GAP_ENCABEZADO_PT = 22

ANCHO_LOGO_PT = 130
ANCHO_ETQ_ENC_PT = 75
# 2 pares etiqueta/valor por fila de encabezado (ver _tabla_encabezado_resumen/_detalle) -- antes
# solo restaba 1x ANCHO_ETQ_ENC_PT en vez de 2x, la tabla terminaba más ancha que el contenido y se
# salía del margen derecho (bug real, reportado por el usuario con una captura de pantalla).
ANCHO_VAL_ENC_PT = (ANCHO_CONTENIDO_PT - ANCHO_LOGO_PT - 2 * ANCHO_ETQ_ENC_PT) / 2

# --- Paleta (igual que ventana_revision.py / Cam_Lens_V2 reporte_pdf.py) ---
NEGRO = colors.HexColor("#1E1E28")
GRIS = colors.HexColor("#8A8A92")
BORDE = colors.HexColor("#1E1E28")
FRANJA = colors.HexColor("#F5F5FA")
ETIQUETA_FONDO = colors.HexColor("#D9D9DE")
VERDE = colors.HexColor("#2FA36B")
AMBAR = colors.HexColor("#E0902E")
ROJO = colors.HexColor("#D9534F")
MORADO = colors.HexColor("#7E57C2")
AZUL = colors.HexColor("#3B82C4")
GRIS_VACIO = colors.HexColor("#C8C8CD")  # "sin datos", no un error

_COLOR_ESTADO = {
    "verde": VERDE, "amarillo": AMBAR, "ambar": AMBAR, "rojo": ROJO, "morado": MORADO,
    "base_desactualizada": AZUL, "ok": VERDE, "caido": ROJO,
}

_ESTILO_ETQ = ParagraphStyle(
    "etq", fontName="Helvetica-Bold", fontSize=8, textColor=NEGRO, alignment=TA_CENTER,
)
_ESTILO_VAL = ParagraphStyle(
    "val", fontName="Helvetica-Bold", fontSize=9, textColor=NEGRO, alignment=TA_CENTER,
)
_ESTILO_BANDA = ParagraphStyle(
    "banda", fontName="Helvetica-Bold", fontSize=9, textColor=colors.white, alignment=TA_CENTER,
)
_ESTILO_ENCABEZADO_VAL = ParagraphStyle(
    "encab_val", fontName="Helvetica", fontSize=9, textColor=NEGRO, alignment=TA_CENTER,
)
_ESTILO_PIE = ParagraphStyle("pie", fontName="Helvetica", fontSize=7.5, textColor=GRIS)
_ESTILO_PIE_CENTRO = ParagraphStyle("pie_centro", parent=_ESTILO_PIE, alignment=TA_CENTER)
_ESTILO_PIE_DER = ParagraphStyle(
    "pie_der", fontName="Helvetica", fontSize=7.5, textColor=GRIS, alignment=TA_RIGHT,
)
_ESTILO_TITULO_SECCION = ParagraphStyle(
    "titulo_seccion", fontName="Helvetica-Bold", fontSize=13, textColor=colors.white,
    alignment=TA_CENTER,
)


@dataclass
class MetricaServidor:
    """Un valor de CPU/GPU para un servidor ese día -- `None` si no hubo datos."""
    valor_c: float | None
    estado: str | None  # "verde" | "amarillo" | "rojo" | None (sin datos)


@dataclass
class MontajeDisco:
    punto_montaje: str
    porcentaje: float
    estado: str  # "verde" | "amarillo" | "rojo"


@dataclass
class CamaraFalla:
    camara: str
    estado: str  # color de la celda -- "rojo" | "ambar" | "morado" | "base_desactualizada"
    etiqueta: str  # texto que se muestra en "Estado" (ej. "Cámara sin respuesta") -- descriptivo, no el color crudo
    motivo: str  # detalle técnico, sin el código de error final (no es relevante para el cliente,
    # ver datos_reporte._sin_codigo_error -- ROADMAP.md 28/10/2026)
    ruta_base: Path | None = None  # None = sin imagen que mostrar (ej. cámara sin respuesta ese día)
    ruta_actual: Path | None = None
    # Campos que cambiaron en la configuración (mismo formato que config_compare.compare():
    # {categoria, campo, base, actual}) -- se usa en vez de ruta_base/ruta_actual para "Cambió la
    # configuración" (ROADMAP.md, 28/10/2026): ahí no hay 2 imágenes que mostrar, son 2 paneles de
    # texto con los campos que cambiaron, igual que en `ui/ventana_revision.pedir_revision_config()`.
    config_diferencias: list[dict] | None = None


@dataclass
class ResumenServidor:
    nombre: str
    planta: str
    cpu: MetricaServidor | None  # None = servidor no encontrado en Monit_Servers_V2
    gpu: MetricaServidor | None
    discos: list[MontajeDisco]
    camaras_totales: int
    camaras_ok: int
    camaras_no_concluyentes: int  # ámbar de 1-2 días -- al 3ro pasa a "fallas" (ver datos_reporte.py)
    fallas: list[CamaraFalla] = field(default_factory=list)
    # (puerto, estado) por cada puerto de IA conocido de este servidor ese día -- estado "ok"/"caido"
    # (ver persistencia/db.py, servicio_ia). Lista vacía = nunca se conoció un puerto para este
    # servidor (caso excepcional, ver _texto_vision_stream). ROADMAP.md, 28/10/2026.
    vision_stream: list[tuple[int, str]] = field(default_factory=list)


def _p(texto: str, estilo: ParagraphStyle) -> Paragraph:
    return Paragraph(texto, estilo)


def _celda_estado(etiqueta: str, color: colors.Color | None = None) -> Paragraph:
    estilo = ParagraphStyle(
        "val_color", parent=_ESTILO_VAL, textColor=color if color is not None else NEGRO,
    )
    return _p(etiqueta, estilo)


def _estilo_base_tabla(*, banda_colspan: int, filas: int) -> list[tuple]:
    cmds = [
        ("GRID", (0, 0), (-1, -1), 0.75, BORDE),
        # Mismo borde externo grueso que ya tiene el encabezado (_estilo_encabezado) -- pedido del
        # usuario, 28/10/2026, para que las tablas se vean consistentes entre sí. Van los índices
        # literales (0 / -1) Y las palabras clave "splitfirst"/"splitlast" a la vez -- no son
        # intercambiables: ReportLab ignora por completo "splitfirst"/"splitlast" cuando la tabla
        # termina cabiendo en una sola hoja (ver _drawLines en tables.py), así que sin los literales
        # una tabla corta se quedaba sin borde arriba/abajo. Y un BOX/LINEABOVE/LINEBELOW literal
        # por sí solo no sobrevive el corte entre hojas (el pedazo de arriba se queda sin borde de
        # abajo y el de abajo sin borde de arriba) -- de ahí que haga falta también la versión
        # simbólica, que ReportLab solo resuelve en el punto de corte real. Confirmado con un PDF de
        # prueba mínimo cubriendo ambos casos (tabla que no corta y tabla que sí corta).
        ("LINEBEFORE", (0, 0), (0, -1), 1.75, BORDE),
        ("LINEAFTER", (-1, 0), (-1, -1), 1.75, BORDE),
        ("LINEABOVE", (0, 0), (-1, 0), 1.75, BORDE),
        ("LINEBELOW", (0, -1), (-1, -1), 1.75, BORDE),
        ("LINEABOVE", (0, "splitfirst"), (-1, "splitfirst"), 1.75, BORDE),
        ("LINEBELOW", (0, "splitlast"), (-1, "splitlast"), 1.75, BORDE),
        ("SPAN", (0, 0), (banda_colspan - 1, 0)),
        ("BACKGROUND", (0, 0), (banda_colspan - 1, 0), NEGRO),
        # Fila 1 son siempre los títulos de columna (Servidor/CPU/..., Cámara/Estado/Motivo,
        # Servicios/Puertos...) en las 3 tablas que usan este estilo -- mismo gris que las etiquetas
        # del encabezado (ETIQUETA_FONDO), en vez de perderse en el rayado blanco/franja normal de
        # las filas de datos (pedido del usuario, 28/10/2026).
        ("BACKGROUND", (0, 1), (-1, 1), ETIQUETA_FONDO),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    for fila in range(2, filas):
        if fila % 2 == 1:
            cmds.append(("BACKGROUND", (0, fila), (-1, fila), FRANJA))
    return cmds


_ANCHO_ENC_COLS = [ANCHO_LOGO_PT, ANCHO_ETQ_ENC_PT, ANCHO_VAL_ENC_PT, ANCHO_ETQ_ENC_PT, ANCHO_VAL_ENC_PT]


def _fila_campos(etq1: str, val1: str, etq2: str, val2: str) -> list[Paragraph]:
    return [
        _p(etq1, _ESTILO_ETQ), _p(val1, _ESTILO_ENCABEZADO_VAL),
        _p(etq2, _ESTILO_ETQ), _p(val2, _ESTILO_ENCABEZADO_VAL),
    ]


def _estilo_encabezado(*, filas: int) -> TableStyle:
    cmds = [
        ("GRID", (0, 0), (-1, -1), 0.75, BORDE),
        ("BOX", (0, 0), (-1, -1), 1.75, BORDE),
        ("BACKGROUND", (1, 0), (1, filas - 1), ETIQUETA_FONDO),
        ("BACKGROUND", (3, 0), (3, filas - 1), ETIQUETA_FONDO),
        ("ALIGN", (0, 0), (0, filas - 1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    if filas > 1:
        cmds.append(("SPAN", (0, 0), (0, filas - 1)))
    return TableStyle(cmds)


def _tabla_encabezado_resumen(cliente: str, fecha: date) -> Table:
    """Hoja 1 (resumen de todos los servidores): no hay un solo servidor ni una sola planta que
    mostrar -- cada fila de la tabla de resumen ya trae la suya (ver _tabla_resumen_servidores)."""
    logo = Image(str(LOGO), width=90, height=70.6)
    data = [[logo] + _fila_campos("CLIENTE", cliente, "FECHA", fecha.strftime("%d/%m/%Y"))]
    t = Table(data, colWidths=_ANCHO_ENC_COLS)
    t.setStyle(_estilo_encabezado(filas=1))
    return t


def _tabla_encabezado_detalle(cliente: str, planta: str, fecha: date, servidor: str) -> Table:
    """Hojas de detalle por servidor: aquí sí hay un servidor y una planta concretos."""
    logo = Image(str(LOGO), width=90, height=70.6)
    data = [
        [logo] + _fila_campos("CLIENTE", cliente, "PLANTA", planta),
        [""] + _fila_campos("FECHA", fecha.strftime("%d/%m/%Y"), "SERVIDOR", servidor),
    ]
    t = Table(data, colWidths=_ANCHO_ENC_COLS)
    t.setStyle(_estilo_encabezado(filas=2))
    return t


_SIMBOLOGIA_RESUMEN = [
    # Para la hoja 1 (sección de servidores) -- describe únicamente los colores que de verdad
    # aparecen ahí (CPU/GPU/Disco): el detalle de cámaras usa su propia simbología, ver
    # `_SIMBOLOGIA_DETALLE` (ROADMAP.md, 28/10/2026 -- antes esta misma lista mezclaba los
    # significados de las dos secciones, y morado/azul no se usan para nada en esta hoja).
    (VERDE, "OK"),
    (AMBAR, "Cerca del umbral"),
    (ROJO, "Requiere revisión inmediata"),
    (GRIS, "Sin datos de monitoreo"),
]
_SIMBOLOGIA_DETALLE = [
    # Para el pie de las hojas de detalle por servidor (ROADMAP.md, 28/10/2026) -- es la simbología
    # original de 6 colores que tenía la hoja de resumen antes de separarla; se reutiliza tal cual
    # aquí, a pedido del usuario.
    (VERDE, "OK"),
    (AMBAR, "No concluyente (1-2 días) / configuración no disponible"),
    (ROJO, "Falla confirmada / cámara o imagen sin respuesta"),
    (MORADO, "Pendiente de revisión"),
    (AZUL, "Base de imágenes desactualizada"),
    (GRIS, "Sin datos de monitoreo"),
]
_ESTILO_SIMBOLOGIA = ParagraphStyle(
    "simbologia", fontName="Helvetica", fontSize=7.5, textColor=NEGRO, alignment=TA_CENTER,
)


def _texto_simbologia(simbologia: list[tuple]) -> Paragraph:
    """Cada entrada (bala + etiqueta) va con espacios duros adentro -- para que, si no cabe todo en
    una sola línea, el salto caiga ENTRE entradas y no a la mitad de una etiqueta de varias palabras
    (bug real reportado por el usuario: "Base de" quedaba en una línea e "imágenes desactualizada"
    en la siguiente). El espacio normal queda solo como separador entre entradas -- ahí sí puede
    saltar de línea."""
    partes = [
        f'<font color="{color.hexval()}">■</font>&nbsp;{etiqueta.replace(" ", "&nbsp;")}'
        for color, etiqueta in simbologia
    ]
    # Separador entre entradas: varios espacios duros (ancho garantizado, para que el cuadro de
    # color de una entrada no se vea pegado al texto de la anterior) + uno normal al final, el
    # único punto donde se permite el salto de línea entre entradas (pedido del usuario, 28/10/2026).
    return Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; ".join(partes), _ESTILO_SIMBOLOGIA)


def _tabla_pie(cliente: str, num_hoja: int, total_hojas: int, simbologia: list[tuple]) -> Table:
    """Pie de página con su línea de simbología arriba (qué significa cada color) -- ambas
    secciones del reporte la llevan, cada una con la suya (`_SIMBOLOGIA_RESUMEN`/
    `_SIMBOLOGIA_DETALLE`, ROADMAP.md 28/10/2026): antes solo la hoja de resumen la tenía."""
    fila_pie = [
        _p("Quantum Labs Computer Vision", _ESTILO_PIE),
        _p(f"Hoja {num_hoja} de {total_hojas}", _ESTILO_PIE_CENTRO),
        _p(cliente, _ESTILO_PIE_DER),
    ]
    t = Table(
        [[_texto_simbologia(simbologia), "", ""], fila_pie],
        colWidths=[ANCHO_CONTENIDO_PT / 3] * 3,
    )
    t.setStyle(TableStyle([
        ("SPAN", (0, 0), (-1, 0)),
        ("LINEABOVE", (0, 0), (-1, 0), 0.75, BORDE),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
    ]))
    return t


def _texto_metrica(metrica: MetricaServidor | None) -> Paragraph:
    if metrica is None or metrica.valor_c is None:
        return _celda_estado("Sin datos", GRIS)
    return _celda_estado(f"{metrica.valor_c:.1f} °C", _COLOR_ESTADO.get(metrica.estado))


_ESTILO_DISCO_NOMBRE = ParagraphStyle(
    "disco_nombre", fontName="Helvetica-Bold", fontSize=8, textColor=NEGRO, alignment=TA_LEFT,
)


def _texto_discos(discos: list[MontajeDisco], ancho_pt: float) -> Table | Paragraph:
    """Nombre del punto de montaje a la izquierda, porcentaje a la derecha (coloreado según su
    semáforo) -- más fácil de comparar de un vistazo que centrado (pedido 21/10/2026)."""
    if not discos:
        return _celda_estado("Sin datos", GRIS)
    filas = []
    for d in discos:
        color = _COLOR_ESTADO.get(d.estado, NEGRO)
        estilo_pct = ParagraphStyle("disco_pct", fontName="Helvetica-Bold", fontSize=8, textColor=color, alignment=TA_RIGHT)
        filas.append([_p(d.punto_montaje, _ESTILO_DISCO_NOMBRE), _p(f"{d.porcentaje:.0f}%", estilo_pct)])
    t = Table(filas, colWidths=[ancho_pt * 0.65, ancho_pt * 0.35])
    t.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def _imagen_proporcional(path: Path, ancho_pt: float) -> Image | None:
    """Carga la imagen con la misma cuadrícula guía que `ventana_revision.py` (ayuda a juzgar a
    ojo si la cámara se movió), con la proporción real del archivo -- nunca un ratio fijo a ojo.

    `None` si el archivo está dañado (más allá de los avisos inofensivos de "Corrupt JPEG data",
    ver `_abrir_imagen_segura`) -- antes esto tumbaba la generación completa del PDF en vez de
    omitir solo esa imagen (bug real, 26/10/2026)."""
    img = _abrir_imagen_segura(path)
    if img is None:
        return None
    img = _con_cuadricula(img)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85)
    buf.seek(0)
    alto_pt = ancho_pt * img.height / img.width
    return Image(buf, width=ancho_pt, height=alto_pt)


_GUTTER_IMAGENES_PT = 5  # pedido del usuario, 28/10/2026 -- antes 10, se sentía grande
_ESTILO_IMAGEN_NO_DISPONIBLE = ParagraphStyle(
    "img_no_disp", fontName="Helvetica-Oblique", fontSize=8.5, textColor=GRIS, alignment=TA_CENTER,
)


def _celda_imagen(path: Path, ancho_pt: float):
    return _imagen_proporcional(path, ancho_pt) or _p("Imagen no disponible (archivo dañado)", _ESTILO_IMAGEN_NO_DISPONIBLE)


def _fila_imagenes(ruta_base: Path, ruta_actual: Path) -> Table:
    # Columnas de margen (0 y 4) del mismo ancho que el gutter entre los 2 recuadros (2) -- sin
    # esto, los recuadros quedaban pegados al margen de la página mientras que entre ellos sí había
    # separación (pedido del usuario, 28/10/2026).
    ancho_img = (ANCHO_CONTENIDO_PT - 3 * _GUTTER_IMAGENES_PT) / 2
    data = [
        ["", _p("Base", _ESTILO_ETQ), "", _p("Actual", _ESTILO_ETQ), ""],
        ["", _celda_imagen(ruta_base, ancho_img), "", _celda_imagen(ruta_actual, ancho_img), ""],
    ]
    t = Table(
        data,
        colWidths=[_GUTTER_IMAGENES_PT, ancho_img, _GUTTER_IMAGENES_PT, ancho_img, _GUTTER_IMAGENES_PT],
    )
    t.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (1, 0), (1, -1), 0.75, BORDE),
        ("BOX", (3, 0), (3, -1), 0.75, BORDE),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return t


_ESTILO_CONFIG_DIFF = ParagraphStyle(
    "config_diff", fontName="Helvetica", fontSize=8, textColor=NEGRO, alignment=TA_LEFT, leading=11,
)


def _texto_config_diff(diferencias: list[dict], clave_valor: str) -> Paragraph:
    """`clave_valor` es `"base"` o `"actual"` -- la misma lista de diferencias alimenta los 2
    paneles, cada uno mostrando su propio lado (ROADMAP.md, 28/10/2026, igual criterio que
    `ui/ventana_revision.pedir_revision_config()`: agrupado por categoría, solo los campos que
    cambiaron, nunca el .json completo)."""
    por_categoria: dict[str, list[dict]] = {}
    for d in diferencias:
        por_categoria.setdefault(d["categoria"], []).append(d)
    lineas = []
    for categoria, items in sorted(por_categoria.items()):
        lineas.append(f"<b>{categoria}</b>")
        lineas.extend(f"{item['campo']}: {item[clave_valor]}" for item in items)
    return _p("<br/>".join(lineas) if lineas else "(sin cambios)", _ESTILO_CONFIG_DIFF)


def _fila_config_diff(diferencias: list[dict]) -> Table:
    # Mismas columnas de margen que _fila_imagenes(), y por la misma razón (ROADMAP.md, 28/10/2026).
    ancho_panel = (ANCHO_CONTENIDO_PT - 3 * _GUTTER_IMAGENES_PT) / 2
    data = [
        ["", _p("Configuración Base", _ESTILO_ETQ), "", _p("Configuración Hoy", _ESTILO_ETQ), ""],
        ["", _texto_config_diff(diferencias, "base"), "", _texto_config_diff(diferencias, "actual"), ""],
    ]
    t = Table(
        data,
        colWidths=[_GUTTER_IMAGENES_PT, ancho_panel, _GUTTER_IMAGENES_PT, ancho_panel, _GUTTER_IMAGENES_PT],
    )
    t.setStyle(TableStyle([
        ("ALIGN", (1, 0), (3, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (1, 0), (1, -1), 0.75, BORDE),
        ("BOX", (3, 0), (3, -1), 0.75, BORDE),
        ("TOPPADDING", (0, 0), (-1, 0), 4), ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
        ("TOPPADDING", (0, 1), (-1, 1), 6), ("BOTTOMPADDING", (0, 1), (-1, 1), 6),
        ("LEFTPADDING", (1, 1), (1, 1), 8), ("LEFTPADDING", (3, 1), (3, 1), 8),
        ("RIGHTPADDING", (1, 1), (1, 1), 8), ("RIGHTPADDING", (3, 1), (3, 1), 8),
        ("LEFTPADDING", (0, 0), (-1, 0), 0), ("RIGHTPADDING", (0, 0), (-1, 0), 0),
    ]))
    return t


_ANCHO_COL_DISCOS_PT = ANCHO_CONTENIDO_PT * 0.18


def _clave_orden_servidor(cliente: str, nombre: str) -> tuple:
    """Orden por nombre de servidor (pedido 21/10/2026) -- antes era planta primero. Caso especial
    de AbInBev: sus servidores mezclan dos prefijos (QLYMSPROD/QBYMSPROD) pero el orden que importa
    es el de los últimos dígitos (01, 02, ..., 11) sin importar el prefijo -- alfabético normal los
    pondría mal (QBYMSPROD07 antes que QLYMSPROD01, por la "B" vs. "L"). Los demás clientes usan
    orden alfabético simple."""
    if cliente == "AbInBev":
        m = re.search(r"(\d+)$", nombre)
        if m:
            return (0, int(m.group(1)))
    return (1, nombre)


def _tabla_resumen_servidores(cliente: str, servidores: list[ResumenServidor]) -> Table:
    servidores = sorted(servidores, key=lambda s: _clave_orden_servidor(cliente, s.nombre))
    encabezados = [
        _p(t, _ESTILO_ETQ) for t in
        ["Servidor", "CPU", "GPU", "Disco(s)", "Cámaras\ntotales", "Cámaras\nOK",
         "No\nconcluyente", "Cámaras\ncon falla"]
    ]
    data = [[_p("RESUMEN DE SERVIDORES", _ESTILO_BANDA)] + [""] * 7, encabezados]
    for s in servidores:
        # Cámaras distintas, no filas de falla -- una misma cámara puede tener una fila por imagen
        # y otra por configuración (ejes independientes, ROADMAP.md 28/10/2026); sin esto el conteo
        # podía superar camaras_totales.
        n_fallas = len({f.camara for f in s.fallas})
        # Las 4 columnas de conteo de cámaras van siempre en negro (ROADMAP.md, 28/10/2026) -- un
        # color ahí se confundía con la simbología del pie (que ahora describe CPU/GPU/Disco, no
        # cámaras). El detalle de qué cámara tiene qué problema ya vive en la sección siguiente.
        data.append([
            _p(f"{s.nombre}<br/><font size=7 color='#8A8A92'>{s.planta}</font>", _ESTILO_VAL),
            _texto_metrica(s.cpu),
            _texto_metrica(s.gpu),
            _texto_discos(s.discos, _ANCHO_COL_DISCOS_PT - 12),  # -12: el LEFT/RIGHTPADDING de la celda
            _celda_estado(str(s.camaras_totales)),
            _celda_estado(str(s.camaras_ok)),
            _celda_estado(str(s.camaras_no_concluyentes)),
            _celda_estado(str(n_fallas)),
        ])
    anchos = [ANCHO_CONTENIDO_PT * f for f in (0.19, 0.11, 0.11, 0.18, 0.09, 0.09, 0.11, 0.12)]
    t = Table(data, colWidths=anchos)
    t.setStyle(TableStyle(_estilo_base_tabla(banda_colspan=8, filas=len(data))))
    return t


def _texto_vision_stream(vision_stream: list[tuple[int, str]]) -> Paragraph:
    """Todos los puertos de IA conocidos de un servidor en una sola celda, cada uno coloreado según
    su propio estado ese día (un servidor puede tener más de uno, ej. Api_Manzanillo con 4) --
    "Puerto Desconocido" en el caso excepcional de que nunca se haya conocido ninguno (ROADMAP.md,
    28/10/2026)."""
    if not vision_stream:
        return _celda_estado("Puerto Desconocido")
    partes = [
        f'<font color="{_COLOR_ESTADO.get(estado, NEGRO).hexval()}">{puerto}</font>'
        for puerto, estado in sorted(vision_stream)
    ]
    return _p(", ".join(partes), _ESTILO_VAL)


def _tabla_vision_stream(servidor: ResumenServidor) -> Table:
    data = [
        [_p("SISTEMA DE VISIÓN-STREAM", _ESTILO_BANDA), ""],
        [_p(f"Servicios en {servidor.nombre}", _ESTILO_ETQ), _p("Puerto(s) Utilizado(s)", _ESTILO_ETQ)],
        [_p("Vision-Stream", _ESTILO_VAL), _texto_vision_stream(servidor.vision_stream)],
    ]
    anchos = [ANCHO_CONTENIDO_PT * 0.5, ANCHO_CONTENIDO_PT * 0.5]
    t = Table(data, colWidths=anchos)
    t.setStyle(TableStyle(_estilo_base_tabla(banda_colspan=2, filas=len(data))))
    return t


def _tabla_fallas_servidor(servidor: ResumenServidor) -> Table:
    # Sin repetir servidor/planta en la banda -- ya están en el encabezado de la hoja
    # (_tabla_encabezado_detalle).
    data = [
        [_p("CÁMARAS CON FALLA", _ESTILO_BANDA), "", ""],
        [_p("Cámara", _ESTILO_ETQ), _p("Estado", _ESTILO_ETQ), _p("Motivo", _ESTILO_ETQ)],
    ]
    filas_imagenes: list[int] = []
    for f in servidor.fallas:
        data.append([
            _p(f.camara, _ESTILO_VAL),
            _celda_estado(f.etiqueta, _COLOR_ESTADO.get(f.estado)),
            _p(f.motivo, ParagraphStyle("motivo", parent=_ESTILO_VAL, alignment=1)),
        ])
        # Sin imagen que mostrar para fallas que no vienen de comparar imagen (ej. cámara sin
        # respuesta ese día -- no hay "actual" que capturar). Pedido 21/10/2026.
        if f.ruta_base is not None and f.ruta_actual is not None:
            filas_imagenes.append(len(data))
            data.append([_fila_imagenes(f.ruta_base, f.ruta_actual), "", ""])
        elif f.config_diferencias is not None:
            # "Cambió la configuración" (ROADMAP.md, 28/10/2026) -- mismo tratamiento visual que la
            # fila de imágenes (span completo, sin fondo ni padding de la banda), pero con los 2
            # paneles de texto en vez de 2 fotos.
            filas_imagenes.append(len(data))
            data.append([_fila_config_diff(f.config_diferencias), "", ""])

    anchos = [ANCHO_CONTENIDO_PT * f for f in (0.22, 0.16, 0.62)]
    t = Table(data, colWidths=anchos)
    estilo = _estilo_base_tabla(banda_colspan=3, filas=len(data))
    for fila_idx in filas_imagenes:
        estilo.append(("SPAN", (0, fila_idx), (2, fila_idx)))
        estilo.append(("BACKGROUND", (0, fila_idx), (2, fila_idx), colors.white))
        # Sin esto, el LEFT/RIGHTPADDING de 6pt heredado de _estilo_base_tabla se suma al ancho
        # completo con el que ya está armada _fila_imagenes(), y el borde derecho se sale del
        # recuadro (bug real, visto en un PDF: la imagen "Actual" se salía del marco).
        estilo.append(("LEFTPADDING", (0, fila_idx), (2, fila_idx), 0))
        estilo.append(("RIGHTPADDING", (0, fila_idx), (2, fila_idx), 0))
        # Arriba/abajo del recuadro, el mismo espacio que ya hay a los lados y al centro (pedido del
        # usuario, 28/10/2026 -- para que el recuadro quede simétrico en las 4 direcciones).
        estilo.append(("TOPPADDING", (0, fila_idx), (2, fila_idx), _GUTTER_IMAGENES_PT))
        estilo.append(("BOTTOMPADDING", (0, fila_idx), (2, fila_idx), _GUTTER_IMAGENES_PT))
    t.setStyle(TableStyle(estilo))
    return t


def _dibujar_encabezado_pie(canvas, encabezado: Table, pie: Table) -> None:
    canvas.saveState()
    w, h = encabezado.wrap(ANCHO_CONTENIDO_PT, letter[1])
    encabezado.drawOn(canvas, MARGEN_PT, letter[1] - MARGEN_PT - h)
    w, h = pie.wrap(ANCHO_CONTENIDO_PT, 200)
    pie.drawOn(canvas, MARGEN_PT, MARGEN_PT)
    canvas.restoreState()


def construir_pdf(cliente: str, fecha: date, servidores: list[ResumenServidor], ruta_salida: Path) -> None:
    """Arma y guarda el PDF ejecutivo de un cliente: hoja 1 con el resumen de todos sus
    servidores (encabezado Cliente/Fecha -- no hay un solo servidor/planta que mostrar ahí), luego
    una sección por cada servidor que tenga algo que reportar -- una cámara en falla, o su
    Vision-Stream con al menos un puerto caído (ROADMAP.md, 28/10/2026; antes solo entraba aquí un
    servidor con cámaras en falla) -- con encabezado Cliente/Planta/Fecha/Servidor, ya concreto.
    Cada servidor usa su propio `PageTemplate` -- si su contenido se desborda a una segunda hoja
    física, esa continuación repite el mismo encabezado (misma lógica que ReportLab ya usa para el
    pie: sigue aplicando el último `PageTemplate` activo hasta que aparezca un `NextPageTemplate`
    nuevo)."""
    def _necesita_hoja_detalle(s: ResumenServidor) -> bool:
        return bool(s.fallas) or any(estado == "caido" for _puerto, estado in s.vision_stream)

    # Mismo orden que _tabla_resumen_servidores (incluye el caso especial de AbInBev) -- antes esta
    # lista se quedaba en el orden alfabético simple de la consulta SQL, así que el resumen salía
    # bien ordenado pero las hojas de detalle por servidor no (bug real, reportado 22/10/2026).
    servidores_con_detalle = sorted(
        (s for s in servidores if _necesita_hoja_detalle(s)),
        key=lambda s: _clave_orden_servidor(cliente, s.nombre),
    )

    # Los dos encabezados tienen alturas distintas (1 fila vs. 2), y los dos pies también (cada uno
    # trae su propia línea de simbología, de distinto largo -- ROADMAP.md 28/10/2026) -- cada tipo
    # de hoja necesita su propio alto de marco, calculado con datos de muestra (el alto no depende
    # del contenido real: son párrafos de una sola línea con fuente fija).
    alto_enc_resumen = _tabla_encabezado_resumen(cliente, fecha).wrap(ANCHO_CONTENIDO_PT, letter[1])[1]
    alto_enc_detalle = _tabla_encabezado_detalle(cliente, "X", fecha, "X").wrap(ANCHO_CONTENIDO_PT, letter[1])[1]
    alto_pie_resumen = _tabla_pie(cliente, 1, 1, _SIMBOLOGIA_RESUMEN).wrap(ANCHO_CONTENIDO_PT, 200)[1]
    alto_pie_detalle = _tabla_pie(cliente, 1, 1, _SIMBOLOGIA_DETALLE).wrap(ANCHO_CONTENIDO_PT, 200)[1]
    frame_alto_resumen = (
        letter[1] - 2 * MARGEN_PT - alto_enc_resumen - alto_pie_resumen - _GAP_ENCABEZADO_PT
    )
    frame_alto_detalle = letter[1] - 2 * MARGEN_PT - alto_enc_detalle - alto_pie_detalle - _GAP_ENCABEZADO_PT

    # Total de hojas no se sabe de antemano (el flujo de ReportLab decide cuántas hacen falta para
    # el detalle) -- se resuelve con un primer `build` mudo y el conteo real de páginas.
    contador_paginas = {"total": 1}

    def _on_resumen(canvas, doc):
        encabezado = _tabla_encabezado_resumen(cliente, fecha)
        pie = _tabla_pie(cliente, canvas.getPageNumber(), contador_paginas["total"], _SIMBOLOGIA_RESUMEN)
        _dibujar_encabezado_pie(canvas, encabezado, pie)

    def _hacer_on_detalle(servidor: ResumenServidor):
        def _on_detalle(canvas, doc):
            encabezado = _tabla_encabezado_detalle(cliente, servidor.planta, fecha, servidor.nombre)
            pie = _tabla_pie(cliente, canvas.getPageNumber(), contador_paginas["total"], _SIMBOLOGIA_DETALLE)
            _dibujar_encabezado_pie(canvas, encabezado, pie)
        return _on_detalle

    def _nuevo_doc() -> BaseDocTemplate:
        frame_resumen = Frame(
            MARGEN_PT, MARGEN_PT + alto_pie_resumen, ANCHO_CONTENIDO_PT, frame_alto_resumen,
            id="f_resumen", topPadding=0, bottomPadding=0, leftPadding=0, rightPadding=0,
        )
        plantillas = [PageTemplate(id="resumen", frames=[frame_resumen], onPage=_on_resumen)]
        for i, s in enumerate(servidores_con_detalle):
            frame_detalle = Frame(
                MARGEN_PT, MARGEN_PT + alto_pie_detalle, ANCHO_CONTENIDO_PT, frame_alto_detalle,
                id=f"f_detalle_{i}", topPadding=0, bottomPadding=0, leftPadding=0, rightPadding=0,
            )
            plantillas.append(
                PageTemplate(id=f"detalle_{i}", frames=[frame_detalle], onPage=_hacer_on_detalle(s))
            )
        doc = BaseDocTemplate(
            str(ruta_salida), pagesize=letter,
            leftMargin=MARGEN_PT, rightMargin=MARGEN_PT, topMargin=MARGEN_PT, bottomMargin=MARGEN_PT,
        )
        doc.addPageTemplates(plantillas)
        return doc

    def _armar_story() -> list:
        story = [_tabla_resumen_servidores(cliente, servidores)]
        for i, s in enumerate(servidores_con_detalle):
            story.append(NextPageTemplate(f"detalle_{i}"))
            story.append(PageBreak())
            story.append(_tabla_vision_stream(s))
            story.append(Spacer(1, 10))
            if s.fallas:
                story.append(_tabla_fallas_servidor(s))
                story.append(Spacer(1, 10))
        return story

    doc = _nuevo_doc()
    doc.build(_armar_story())
    contador_paginas["total"] = doc.page
    doc = _nuevo_doc()
    doc.build(_armar_story())
