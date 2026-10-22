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

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
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

LOGO = Path(__file__).parent / "assets" / "QuantumLab-Logo-01.png"

MARGEN_PT = 24
ANCHO_CONTENIDO_PT = letter[0] - 2 * MARGEN_PT
_GAP_ENCABEZADO_PT = 22
ALTO_PIE_PT = 20

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
GRIS_VACIO = colors.HexColor("#C8C8CD")  # "sin datos", no un error

_COLOR_ESTADO = {"verde": VERDE, "amarillo": AMBAR, "ambar": AMBAR, "rojo": ROJO, "morado": MORADO}

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
    estado: str  # "morado" | "rojo" | "amarillo" (ámbar solo llega aquí si ya es 3+ días seguidos)
    motivo: str


@dataclass
class ResumenServidor:
    nombre: str
    planta: str
    cpu: MetricaServidor | None  # None = servidor no encontrado en Monit_Servers_V2
    gpu: MetricaServidor | None
    discos: list[MontajeDisco]
    camaras_totales: int
    camaras_ok: int
    fallas: list[CamaraFalla] = field(default_factory=list)


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
        ("SPAN", (0, 0), (banda_colspan - 1, 0)),
        ("BACKGROUND", (0, 0), (banda_colspan - 1, 0), NEGRO),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    for fila in range(1, filas):
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


def _tabla_pie(cliente: str, num_hoja: int, total_hojas: int) -> Table:
    t = Table(
        [[
            _p("Quantum Labs Computer Vision", _ESTILO_PIE),
            _p(f"Hoja {num_hoja} de {total_hojas}", _ESTILO_PIE_CENTRO),
            _p(cliente, _ESTILO_PIE_DER),
        ]],
        colWidths=[ANCHO_CONTENIDO_PT / 3] * 3,
    )
    t.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 0.75, BORDE),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


_SIMBOLOGIA = [
    (VERDE, "OK"),
    (AMBAR, "No concluyente (3+ días seguidos)"),
    (ROJO, "Falla confirmada / servidor sin respuesta"),
    (MORADO, "Pendiente de revisión"),
    (GRIS, "Sin datos de monitoreo"),
]
_ESTILO_SIMBOLOGIA = ParagraphStyle(
    "simbologia", fontName="Helvetica", fontSize=7.5, textColor=NEGRO, alignment=TA_CENTER,
)


def _texto_simbologia() -> Paragraph:
    partes = [f'<font color="{color.hexval()}">■</font> {etiqueta}' for color, etiqueta in _SIMBOLOGIA]
    return Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;".join(partes), _ESTILO_SIMBOLOGIA)


def _tabla_pie_resumen(cliente: str, num_hoja: int, total_hojas: int) -> Table:
    """Solo para la hoja 1 -- agrega una línea de simbología (qué significa cada color) arriba del
    pie normal. En las hojas de detalle no hace falta: ahí el contexto ya es un solo servidor."""
    fila_pie = [
        _p("Quantum Labs Computer Vision", _ESTILO_PIE),
        _p(f"Hoja {num_hoja} de {total_hojas}", _ESTILO_PIE_CENTRO),
        _p(cliente, _ESTILO_PIE_DER),
    ]
    t = Table(
        [[_texto_simbologia(), "", ""], fila_pie],
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


def _texto_discos(discos: list[MontajeDisco]) -> Paragraph:
    if not discos:
        return _celda_estado("Sin datos", GRIS)
    lineas = []
    for d in discos:
        color = _COLOR_ESTADO.get(d.estado, NEGRO)
        lineas.append(f'<font color="{color.hexval()}">{d.punto_montaje} {d.porcentaje:.0f}%</font>')
    return Paragraph("<br/>".join(lineas), ParagraphStyle("discos", parent=_ESTILO_VAL))


def _tabla_resumen_servidores(servidores: list[ResumenServidor]) -> Table:
    encabezados = [
        _p(t, _ESTILO_ETQ) for t in
        ["Servidor", "CPU", "GPU", "Disco(s)", "Cámaras\ntotales", "Cámaras\nOK", "Cámaras\ncon falla"]
    ]
    data = [[_p("RESUMEN DE SERVIDORES", _ESTILO_BANDA)] + [""] * 6, encabezados]
    for s in servidores:
        n_fallas = len(s.fallas)
        color_fallas = ROJO if n_fallas else VERDE
        data.append([
            _p(f"{s.nombre}<br/><font size=7 color='#8A8A92'>{s.planta}</font>", _ESTILO_VAL),
            _texto_metrica(s.cpu),
            _texto_metrica(s.gpu),
            _texto_discos(s.discos),
            _celda_estado(str(s.camaras_totales)),
            _celda_estado(str(s.camaras_ok), VERDE),
            _celda_estado(str(n_fallas), color_fallas),
        ])
    anchos = [ANCHO_CONTENIDO_PT * f for f in (0.22, 0.13, 0.13, 0.20, 0.10, 0.10, 0.12)]
    t = Table(data, colWidths=anchos)
    t.setStyle(TableStyle(_estilo_base_tabla(banda_colspan=7, filas=len(data))))
    return t


def _tabla_fallas_servidor(servidor: ResumenServidor) -> Table:
    # Sin repetir servidor/planta en la banda -- ya están en el encabezado de la hoja
    # (_tabla_encabezado_detalle).
    data = [
        [_p("CÁMARAS CON FALLA", _ESTILO_BANDA), "", ""],
        [_p("Cámara", _ESTILO_ETQ), _p("Estado", _ESTILO_ETQ), _p("Motivo", _ESTILO_ETQ)],
    ]
    for f in servidor.fallas:
        data.append([
            _p(f.camara, _ESTILO_VAL),
            _celda_estado(f.estado.capitalize(), _COLOR_ESTADO.get(f.estado)),
            _p(f.motivo, ParagraphStyle("motivo", parent=_ESTILO_VAL, alignment=1)),
        ])
    anchos = [ANCHO_CONTENIDO_PT * f for f in (0.22, 0.16, 0.62)]
    t = Table(data, colWidths=anchos)
    t.setStyle(TableStyle(_estilo_base_tabla(banda_colspan=3, filas=len(data))))
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
    una sección por servidor con al menos una cámara en falla (encabezado Cliente/Planta/Fecha/
    Servidor, ya concreto). Cada servidor usa su propio `PageTemplate` -- si su tabla de fallas se
    desborda a una segunda hoja física, esa continuación repite el mismo encabezado (misma lógica
    que ReportLab ya usa para el pie: sigue aplicando el último `PageTemplate` activo hasta que
    aparezca un `NextPageTemplate` nuevo)."""
    servidores_con_fallas = [s for s in servidores if s.fallas]

    # Los dos encabezados tienen alturas distintas (1 fila vs. 2) y los dos pies también (el de la
    # hoja 1 trae además la línea de simbología) -- cada tipo de hoja necesita su propio alto de
    # marco, calculado con datos de muestra (el alto no depende del contenido real: son párrafos de
    # una sola línea con fuente fija).
    alto_enc_resumen = _tabla_encabezado_resumen(cliente, fecha).wrap(ANCHO_CONTENIDO_PT, letter[1])[1]
    alto_enc_detalle = _tabla_encabezado_detalle(cliente, "X", fecha, "X").wrap(ANCHO_CONTENIDO_PT, letter[1])[1]
    alto_pie_resumen = _tabla_pie_resumen(cliente, 1, 1).wrap(ANCHO_CONTENIDO_PT, 200)[1]
    frame_alto_resumen = (
        letter[1] - 2 * MARGEN_PT - alto_enc_resumen - alto_pie_resumen - _GAP_ENCABEZADO_PT
    )
    frame_alto_detalle = letter[1] - 2 * MARGEN_PT - alto_enc_detalle - ALTO_PIE_PT - _GAP_ENCABEZADO_PT

    # Total de hojas no se sabe de antemano (el flujo de ReportLab decide cuántas hacen falta para
    # el detalle) -- se resuelve con un primer `build` mudo y el conteo real de páginas.
    contador_paginas = {"total": 1}

    def _on_resumen(canvas, doc):
        encabezado = _tabla_encabezado_resumen(cliente, fecha)
        pie = _tabla_pie_resumen(cliente, canvas.getPageNumber(), contador_paginas["total"])
        _dibujar_encabezado_pie(canvas, encabezado, pie)

    def _hacer_on_detalle(servidor: ResumenServidor):
        def _on_detalle(canvas, doc):
            encabezado = _tabla_encabezado_detalle(cliente, servidor.planta, fecha, servidor.nombre)
            pie = _tabla_pie(cliente, canvas.getPageNumber(), contador_paginas["total"])
            _dibujar_encabezado_pie(canvas, encabezado, pie)
        return _on_detalle

    def _nuevo_doc() -> BaseDocTemplate:
        frame_resumen = Frame(
            MARGEN_PT, MARGEN_PT + alto_pie_resumen, ANCHO_CONTENIDO_PT, frame_alto_resumen,
            id="f_resumen", topPadding=0, bottomPadding=0, leftPadding=0, rightPadding=0,
        )
        plantillas = [PageTemplate(id="resumen", frames=[frame_resumen], onPage=_on_resumen)]
        for i, s in enumerate(servidores_con_fallas):
            frame_detalle = Frame(
                MARGEN_PT, MARGEN_PT + ALTO_PIE_PT, ANCHO_CONTENIDO_PT, frame_alto_detalle,
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
        story = [_tabla_resumen_servidores(servidores)]
        for i, s in enumerate(servidores_con_fallas):
            story.append(NextPageTemplate(f"detalle_{i}"))
            story.append(PageBreak())
            story.append(_tabla_fallas_servidor(s))
            story.append(Spacer(1, 10))
        return story

    doc = _nuevo_doc()
    doc.build(_armar_story())
    contador_paginas["total"] = doc.page
    doc = _nuevo_doc()
    doc.build(_armar_story())
