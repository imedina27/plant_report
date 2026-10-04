"""Compara la imagen de cada cámara contra una base de referencia, para
detectar si la cámara se movió, quedó obstruida, o sigue igual.

Resume el trabajo de los Experimentos 1-9 documentados en ROADMAP.md, Fase 2.
Resultado de ese trabajo, en una línea: ni la geometría ni el contenido solos
bastan, y ninguno de los dos se debe usar en cascada ("probar A, si falla
probar B") porque a veces ambos se equivocan de la misma forma. Se corren
siempre los dos, y su desacuerdo es en sí mismo una señal de alerta.

- Método 2 (geometría, ORB+RANSAC y correlación de fase): ¿sigue apuntando al
  mismo lugar? Es la señal principal para detectar movimiento.
- Método 1 (contenido, diferencia de píxeles): ¿sigue viendo lo mismo? Señal
  secundaria, para detectar obstrucción total donde la geometría ya no tiene
  nada que medir.

El texto sobreimpreso por la cámara (fecha/hora arriba-izquierda, nombre
abajo-derecha) se tapa antes de medir — Experimento 4: ese texto está fijo en
coordenadas del sensor y no se mueve aunque la cámara gire, y puede secuestrar
la medición con alta confianza (falso negativo) si no se tapa.

La base de un servidor/cámara que no la tiene todavía se crea automáticamente
la primera vez que se procesa (copiando su .jpg de ese día) — Experimento 3:
una base ocupada por un camión/montacargas funciona igual de bien que una
limpia, salvo que el objeto llene casi todo el cuadro (ahí no hay suficiente
fondo estático para medir, y el propio guardia de inliers lo detecta solo).
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import cv2
import numpy as np
from dotenv import load_dotenv

load_dotenv()

CHECK_PLANTS_ROOT = Path(os.environ["CHECK_PLANTS_ROOT"])
IMAGE_BASE_ROOT = Path(os.environ["IMAGE_BASE_ROOT"])

# --- Umbrales validados en los Experimentos 3, 5, 6, 7b y 9 (ver ROADMAP.md) ---
MIN_INLIERS = 100
MIN_CONF_FASE = 0.15  # Experimento 9: queda marcado como pendiente de recalibrar
UMBRAL_DESACUERDO_PX = 15.0
UMBRAL_MOVIMIENTO_PCT = 0.25  # % del ancho de la imagen

# Esquinas donde la cámara sobreimprime fecha/hora y nombre (Experimento 4).
_FRAC_ANCHO_ESQUINA = 0.35
_FRAC_ALTO_ESQUINA = 0.12

_ORB_NFEATURES = 4000


def umbral_para(cliente: str, planta: str, servidor: str, camara: str) -> float:
    """Umbral de movimiento (% del ancho) para una cámara puntual.

    Hoy regresa siempre el umbral global. Punto de enganche para Fase 4: una
    vez que exista `perfil_camara` en la base de datos (ver ROADMAP.md, Fase 4),
    esta función debe consultarlo ahí en vez de regresar la constante — el
    Experimento 8 midió que la misma rotación física produce ~10x más píxeles
    en una escena cercana que en una lejana, así que un umbral único no le
    sirve igual de bien a todas las cámaras.
    """
    return UMBRAL_MOVIMIENTO_PCT


def _imread_unicode(path: Path) -> np.ndarray | None:
    """cv2.imread no soporta rutas con acentos en Windows (usa la API ANSI)."""
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return None
    if not data:
        return None
    return cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)


def _mascara_esquinas(shape: tuple[int, ...]) -> np.ndarray:
    h, w = shape[:2]
    bw, bh = int(w * _FRAC_ANCHO_ESQUINA), int(h * _FRAC_ALTO_ESQUINA)
    mask = np.ones((h, w), dtype=np.uint8)
    mask[:bh, :bw] = 0  # fecha/hora
    mask[h - bh:, w - bw:] = 0  # nombre de camara
    return mask


def _orb_ransac(img1: np.ndarray, img2: np.ndarray, mask: np.ndarray) -> dict:
    i1, i2 = img1.copy(), img2.copy()
    i1[mask == 0] = 0
    i2[mask == 0] = 0
    g1 = cv2.cvtColor(i1, cv2.COLOR_BGR2GRAY)
    g2 = cv2.cvtColor(i2, cv2.COLOR_BGR2GRAY)

    orb = cv2.ORB_create(nfeatures=_ORB_NFEATURES)
    kp1, des1 = orb.detectAndCompute(g1, None)
    kp2, des2 = orb.detectAndCompute(g2, None)
    if des1 is None or des2 is None:
        return {"inliers": 0, "desp": None}

    bf = cv2.BFMatcher(cv2.NORM_HAMMING)
    good = [m for m, n in bf.knnMatch(des1, des2, k=2) if m.distance < 0.75 * n.distance]
    if len(good) < 8:
        return {"inliers": 0, "desp": None}

    p1 = np.float32([kp1[m.queryIdx].pt for m in good])
    p2 = np.float32([kp2[m.trainIdx].pt for m in good])
    H, inlier_mask = cv2.findHomography(p1, p2, cv2.RANSAC, 5.0)
    if H is None:
        return {"inliers": 0, "desp": None}

    inlier_mask = inlier_mask.ravel().astype(bool)
    if inlier_mask.sum() == 0:
        return {"inliers": 0, "desp": None}
    disp = np.linalg.norm(p1[inlier_mask] - p2[inlier_mask], axis=1)
    return {"inliers": int(inlier_mask.sum()), "desp": float(np.mean(disp))}


def _fase_correlate(img1: np.ndarray, img2: np.ndarray, mask: np.ndarray) -> dict:
    g1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY).astype(np.float32)
    g2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY).astype(np.float32)
    media = (g1.mean() + g2.mean()) / 2
    g1c, g2c = g1.copy(), g2.copy()
    g1c[mask == 0] = media
    g2c[mask == 0] = media
    (dx, dy), conf = cv2.phaseCorrelate(g1c, g2c)
    return {"desp": float((dx**2 + dy**2) ** 0.5), "conf": float(conf)}


def _diff_contenido(img1: np.ndarray, img2: np.ndarray, mask: np.ndarray) -> dict:
    i1, i2 = img1.copy(), img2.copy()
    i1[mask == 0] = 0
    i2[mask == 0] = 0
    b1 = cv2.GaussianBlur(i1, (15, 15), 0)
    b2 = cv2.GaussianBlur(i2, (15, 15), 0)
    d = cv2.absdiff(b1, b2)
    return {"mean": float(np.mean(d)), "p95": float(np.percentile(d, 95))}


def evaluar_par(base: np.ndarray, actual: np.ndarray, umbral_pct: float) -> dict:
    """Decide el estado geométrico de un par (base, actual) ya cargados.

    status: "OK" | "REVISAR" | "NO CONCLUYENTE" | "RESOLUCION DISTINTA"
    """
    if base.shape != actual.shape:
        return {"status": "RESOLUCION DISTINTA", "motivo": "resoluciones distintas",
                "orb_inliers": None, "orb_desp": None, "fase_desp": None, "fase_conf": None,
                "contenido_mean": None, "contenido_p95": None}

    mask = _mascara_esquinas(base.shape)
    ancho = base.shape[1]
    umbral_px = (umbral_pct / 100) * ancho

    orb = _orb_ransac(base, actual, mask)
    fase = _fase_correlate(base, actual, mask)
    contenido = _diff_contenido(base, actual, mask)

    orb_ok = orb["inliers"] >= MIN_INLIERS
    fase_ok = fase["conf"] >= MIN_CONF_FASE
    desacuerdo = abs(orb["desp"] - fase["desp"]) if orb["desp"] is not None else None

    if orb_ok and fase_ok:
        if desacuerdo is not None and desacuerdo > UMBRAL_DESACUERDO_PX:
            status, motivo = "REVISAR", "los dos metodos no coinciden"
        elif orb["desp"] < umbral_px:
            status, motivo = "OK", None
        else:
            status, motivo = "REVISAR", "desplazamiento por encima del umbral"
    elif orb_ok:
        status, motivo = ("OK", None) if orb["desp"] < umbral_px else ("REVISAR", "desplazamiento por encima del umbral (solo ORB confiable)")
    elif fase_ok:
        status, motivo = ("OK", None) if fase["desp"] < umbral_px else ("REVISAR", "desplazamiento por encima del umbral (solo fase confiable)")
    else:
        status, motivo = "NO CONCLUYENTE", "ningun metodo alcanza suficiente confianza"

    return {
        "status": status, "motivo": motivo,
        "orb_inliers": orb["inliers"], "orb_desp": orb["desp"],
        "fase_desp": fase["desp"], "fase_conf": fase["conf"],
        "contenido_mean": contenido["mean"], "contenido_p95": contenido["p95"],
    }


# ---------------------------------------------------------------------------
# Base de referencia
# ---------------------------------------------------------------------------

def base_path(cliente: str, planta: str, servidor: str, camara: str) -> Path:
    return IMAGE_BASE_ROOT / cliente / planta / servidor / f"{camara}.jpg"


def load_base(cliente: str, planta: str, servidor: str, camara: str) -> np.ndarray | None:
    path = base_path(cliente, planta, servidor, camara)
    if not path.exists():
        return None
    return _imread_unicode(path)


def save_base(cliente: str, planta: str, servidor: str, camara: str, jpg_path: Path) -> None:
    path = base_path(cliente, planta, servidor, camara)
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(jpg_path, path)


def _marcador_desactualizada(cliente: str, planta: str, servidor: str, camara: str) -> Path:
    return base_path(cliente, planta, servidor, camara).with_suffix(".desactualizada")


def marcar_base_desactualizada(cliente: str, planta: str, servidor: str, camara: str) -> None:
    """Señala que esta base ya no sirve (ver ROADMAP.md, sección 2.8) sin tocar el .jpg.

    No se sustituye de inmediato con la imagen que disparó el REVISAR porque, en el uso diario,
    esa imagen casi siempre tiene un camión/montacargas en cuadro -- hornearla como base
    contaminaría todas las comparaciones futuras. El reemplazo real se hace aparte, cuando
    alguien tenga a mano una imagen limpia (ventana_bases.py o captura.py).
    """
    _marcador_desactualizada(cliente, planta, servidor, camara).touch()


def base_desactualizada(cliente: str, planta: str, servidor: str, camara: str) -> bool:
    return _marcador_desactualizada(cliente, planta, servidor, camara).exists()


def limpiar_marcador_desactualizada(cliente: str, planta: str, servidor: str, camara: str) -> None:
    _marcador_desactualizada(cliente, planta, servidor, camara).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Orquestación por cámara
# ---------------------------------------------------------------------------

def compare_camera_image(jpg_path: Path, cliente: str, planta: str, servidor: str, camara: str) -> dict:
    """Compara la imagen actual de una cámara contra su base, creándola si falta.

    status: "BASE CREADA" | "OK" | "REVISAR" | "NO CONCLUYENTE" | "RESOLUCION DISTINTA"
            | "BASE DESACTUALIZADA"
    """
    base = load_base(cliente, planta, servidor, camara)
    if base is None:
        save_base(cliente, planta, servidor, camara, jpg_path)
        return {"status": "BASE CREADA", "motivo": None,
                "orb_inliers": None, "orb_desp": None, "fase_desp": None, "fase_conf": None,
                "contenido_mean": None, "contenido_p95": None}

    if base_desactualizada(cliente, planta, servidor, camara):
        return {"status": "BASE DESACTUALIZADA",
                "motivo": "pendiente de que alguien suba una imagen limpia (ventana_bases.py)",
                "orb_inliers": None, "orb_desp": None, "fase_desp": None, "fase_conf": None,
                "contenido_mean": None, "contenido_p95": None}

    actual = _imread_unicode(jpg_path)
    if actual is None:
        return {"status": "NO CONCLUYENTE", "motivo": "no se pudo leer la imagen",
                "orb_inliers": None, "orb_desp": None, "fase_desp": None, "fase_conf": None,
                "contenido_mean": None, "contenido_p95": None}

    umbral_pct = umbral_para(cliente, planta, servidor, camara)
    return evaluar_par(base, actual, umbral_pct)
