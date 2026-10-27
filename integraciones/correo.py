"""Envío del reporte ejecutivo por correo (Fase 5, ROADMAP.md).

Un correo por cliente, con todos sus destinatarios juntos en "Para" y el PDF de ese cliente
adjunto -- vía SMTP de Google Workspace con App Password (cuenta y credencial en `.env`, nunca en
el código). Firma HTML con el logo embebido (Content-ID), replicando la tarjeta de contacto real de
Quantum Labs.
"""

from __future__ import annotations

import os
import smtplib
import time
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

LOGO_FIRMA = Path(__file__).parent.parent / "assets" / "QuantumLab-Logo-01.png"

# Reintentos ante errores transitorios (timeout, conexión rechazada) -- no indefinidos (ROADMAP.md,
# sección "manejo de fallos" de Fase 5).
_REINTENTOS = 2
_ESPERA_REINTENTO_S = 5

_FIRMA_HTML = """
<table cellpadding="0" cellspacing="0" style="font-family: Arial, sans-serif; margin-top: 24px;">
  <tr>
    <td style="background-color:#000000; padding:16px;" valign="top">
      <img src="cid:logo_firma" width="130" alt="Quantum Labs">
    </td>
    <td style="padding-left:16px;" valign="top">
      <div style="font-size:15px; font-weight:bold; color:#1E3A5F;">Ismael Medina</div>
      <div style="font-size:12px; color:#E2724B; margin-bottom:8px;">Infrastructure Leader</div>
      <div style="font-size:12px; line-height:18px;">
        <a href="tel:+525586602842" style="color:#1155CC; text-decoration:underline;">t: (55) 8660-2842</a><br>
        <a href="tel:+525151361217" style="color:#1155CC; text-decoration:underline;">c: (55) 5136-1217</a><br>
        <a href="mailto:imedina@quantumlabs.ai" style="color:#1155CC; text-decoration:underline;">m: imedina@quantumlabs.ai</a>
      </div>
      <div style="font-size:12px; color:#333333; margin-top:8px;">
        Insurgentes Sur 1458 Piso 21, 03230, CDMX
      </div>
    </td>
  </tr>
</table>
"""


# Valor especial para REPORTE_DESTINATARIOS_<CLIENTE>: a diferencia de dejar la variable vacía o
# sin poner (que cae al default -- un string vacío es "falso" en Python, así que no se puede
# distinguir de "no configurado"), esto SÍ significa "a este cliente no le mandes nada, a propósito".
_SENTINEL_NO_ENVIAR = "NINGUNO"


def _destinatarios(cliente: str) -> list[str] | None:
    """`REPORTE_DESTINATARIOS_<CLIENTE>` (nombre normalizado a mayúsculas); si no existe o está
    vacía, cae a `REPORTE_DESTINATARIOS_DEFAULT`. Regresa `None` si el valor que terminó aplicando
    -- específico o default, cualquiera de los dos -- es `NINGUNO` (no enviarle correo a propósito);
    `[]` si de plano no hay a quién enviarle (ni específico ni default -- probablemente falta
    configurar)."""
    clave = f"REPORTE_DESTINATARIOS_{cliente.upper()}"
    valor = os.environ.get(clave) or os.environ.get("REPORTE_DESTINATARIOS_DEFAULT")
    if valor and valor.strip().upper() == _SENTINEL_NO_ENVIAR:
        return None
    if not valor:
        return []
    return [correo.strip() for correo in valor.split(",") if correo.strip()]


def _sustituir_cliente(plantilla: str, cliente: str) -> str:
    return plantilla.replace("[Cliente]", cliente).replace("[cliente]", cliente)


def _cuerpo_html(cliente: str) -> str:
    texto = _sustituir_cliente(os.environ["REPORTE_CUERPO"], cliente).replace("\n", "<br>")
    cuerpo = f'<div style="font-family: Arial, sans-serif; font-size: 13px; color:#1E1E28;">{texto}</div>'
    return cuerpo + _FIRMA_HTML


def _construir_mensaje(cliente: str, destinatarios: list[str], ruta_pdf: Path) -> MIMEMultipart:
    msg = MIMEMultipart("mixed")
    msg["Subject"] = _sustituir_cliente(os.environ["REPORTE_ASUNTO"], cliente)
    msg["From"] = os.environ["SMTP_USER"]
    msg["To"] = ", ".join(destinatarios)

    relacionado = MIMEMultipart("related")
    relacionado.attach(MIMEText(_cuerpo_html(cliente), "html"))
    logo = MIMEImage(LOGO_FIRMA.read_bytes())
    logo.add_header("Content-ID", "<logo_firma>")
    logo.add_header("Content-Disposition", "inline", filename=LOGO_FIRMA.name)
    relacionado.attach(logo)
    msg.attach(relacionado)

    adjunto = MIMEApplication(ruta_pdf.read_bytes(), _subtype="pdf")
    adjunto.add_header("Content-Disposition", "attachment", filename=ruta_pdf.name)
    msg.attach(adjunto)

    return msg


def _enviar_con_reintentos(destinatarios: list[str], msg: MIMEMultipart) -> tuple[bool, str | None]:
    ultimo_error: str | None = None
    for intento in range(1 + _REINTENTOS):
        try:
            with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.environ["SMTP_PORT"])) as servidor:
                servidor.starttls()
                servidor.login(os.environ["SMTP_USER"], os.environ["SMTP_APP_PASSWORD"])
                servidor.sendmail(os.environ["SMTP_USER"], destinatarios, msg.as_string())
            return True, None
        except (smtplib.SMTPException, OSError) as error:
            ultimo_error = str(error)
            if intento < _REINTENTOS:
                time.sleep(_ESPERA_REINTENTO_S)
    return False, ultimo_error


def enviar_reportes(rutas_por_cliente: dict[str, Path]) -> list[tuple[str, bool, str | None]]:
    """Un correo por cliente (PDF de `rutas_por_cliente[cliente]` adjunto, todos sus destinatarios
    juntos en "Para"). No se detiene si uno falla -- sigue con los demás clientes. Regresa
    `[(cliente, éxito, motivo), ...]` -- `motivo` es `None` en un envío normal exitoso, el texto del
    error si falló, o la razón si se omitió a propósito (`NINGUNO`)."""
    resultados = []
    for cliente, ruta_pdf in rutas_por_cliente.items():
        destinatarios = _destinatarios(cliente)
        if destinatarios is None:
            resultados.append((cliente, True, "omitido -- configurado como NINGUNO"))
            continue
        if not destinatarios:
            resultados.append((cliente, False, "sin destinatarios configurados"))
            continue
        msg = _construir_mensaje(cliente, destinatarios, ruta_pdf)
        exito, error = _enviar_con_reintentos(destinatarios, msg)
        resultados.append((cliente, exito, error))
    return resultados
