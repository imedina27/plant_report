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
from datetime import date
from pathlib import Path

import cv2
import numpy as np
from dotenv import load_dotenv

load_dotenv()

CHECK_PLANTS_ROOT = Path(os.environ["CHECK_PLANTS_ROOT"])
IMAGE_BASE_ROOT = Path(os.environ["IMAGE_BASE_ROOT"])
IMAGE_HISTORY_ROOT = Path(os.environ["IMAGE_HISTORY_ROOT"])

# --- Umbrales validados en los Experimentos 3, 5, 6, 7b y 9 (ver ROADMAP.md) ---
MIN_INLIERS = 100
MIN_CONF_FASE = 0.15  # Experimento 9: queda marcado como pendiente de recalibrar
UMBRAL_DESACUERDO_PX = 15.0
UMBRAL_MOVIMIENTO_PCT = 0.25  # % del ancho de la imagen

# Cuántas fotos recientes se guardan por cámara para construir la futura base por mediana
# (ver ROADMAP.md, 26/10/2026 -- "Diseño propuesto: mejoras a image_compare.py").
N_DIAS_MEDIANA_BASE = 10

# Cuántas desviaciones MAD por debajo de la mediana histórica de nitidez de la propia cámara
# cuentan como sospechoso (convención de Iglewicz & Hoaglin para outliers robustos).
UMBRAL_MAD_NITIDEZ = 3.5

# Umbrales absolutos de "salud de imagen" (0-255 en escala de grises), validados el 26/10/2026
# contra las 217 cámaras reales de producción: el peor caso legítimo encontrado fue varianza 32.4 /
# brillo 26.6 (escena nocturna de poca textura); una obstrucción total simulada dio varianza ~1.9.
UMBRAL_VARIANZA_MINIMA = 15.0
UMBRAL_BRILLO_MINIMO = 15.0
UMBRAL_BRILLO_MAXIMO = 240.0

# Esquinas donde la cámara sobreimprime fecha/hora y nombre (Experimento 4).
_FRAC_ANCHO_ESQUINA = 0.35
_FRAC_ALTO_ESQUINA = 0.12

_ORB_NFEATURES = 4000


def umbral_para(ancho: int, calibrado_px: float | None = None) -> float:
    """Umbral de movimiento en píxeles para una comparación.

    `calibrado_px` es el p95 de los desplazamientos "normales" históricos de esta cámara en
    particular (`perfil_camara.p95_desplazamiento`, ver `persistencia.db.recalcular_perfiles_estadisticos`)
    -- este módulo no sabe nada de la base de datos, el llamador (`main.py`) decide si hay un valor
    calibrado y lo pasa ya calculado.

    Solo puede hacer a una cámara MENOS sensible que el umbral global, nunca más (26/10/2026,
    confirmado con el usuario): si el p95 calibrado es menor al umbral global, se usa el global --
    evita introducir una clase nueva de falsos positivos en cámaras con poco historial calibrado
    todavía. El Experimento 8 midió que la misma rotación física produce ~10x más píxeles en una
    escena cercana que en una lejana, así que un umbral único no le sirve igual de bien a todas.
    """
    umbral_global_px = (UMBRAL_MOVIMIENTO_PCT / 100) * ancho
    if calibrado_px is None:
        return umbral_global_px
    return max(calibrado_px, umbral_global_px)


def imread_unicode(path: Path) -> np.ndarray | None:
    """cv2.imread no soporta rutas con acentos en Windows (usa la API ANSI)."""
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return None
    if not data:
        return None
    return cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)


def imwrite_unicode(path: Path, img: np.ndarray) -> None:
    """Contraparte de `imread_unicode` -- `cv2.imwrite` tampoco soporta rutas con acentos en
    Windows (falla en silencio, sin excepción ni archivo escrito)."""
    ok, buf = cv2.imencode(".jpg", img)
    if not ok:
        raise ValueError(f"No se pudo codificar la imagen para guardarla en {path}")
    path.write_bytes(buf.tobytes())


def _mascara_esquinas(shape: tuple[int, ...]) -> np.ndarray:
    h, w = shape[:2]
    bw, bh = int(w * _FRAC_ANCHO_ESQUINA), int(h * _FRAC_ALTO_ESQUINA)
    mask = np.ones((h, w), dtype=np.uint8)
    mask[:bh, :bw] = 0  # fecha/hora
    mask[h - bh:, w - bw:] = 0  # nombre de camara
    return mask


_SIN_TRANSFORMACION = {"tx": None, "ty": None, "rotacion_deg": None, "escala": None}


def _descomponer_transformacion(p1: np.ndarray, p2: np.ndarray) -> dict:
    """Traduce el desplazamiento de un conjunto de puntos emparejados (inliers de la homografía
    de `_orb_ransac`) a traslación (tx, ty en píxeles), rotación (grados) y escala -- en vez de
    solo el promedio de distancia entre puntos, que no distingue un giro de un desplazamiento
    lineal (ROADMAP.md, 26/10/2026, punto 4 del plan de mejoras a image_compare.py).

    Usa una transformación de similitud (traslación + rotación + escala uniforme, 4 grados de
    libertad) en vez de descomponer la homografía proyectiva completa -- el movimiento real de una
    cámara de seguridad (pan/tilt/giro) se explica bien así, y es más simple de interpretar que
    separar la componente de perspectiva de una homografía completa.
    """
    M, _ = cv2.estimateAffinePartial2D(p1, p2)
    if M is None:
        return _SIN_TRANSFORMACION
    tx, ty = float(M[0, 2]), float(M[1, 2])
    escala = float(np.hypot(M[0, 0], M[1, 0]))
    rotacion_deg = float(np.degrees(np.arctan2(M[1, 0], M[0, 0])))
    return {"tx": tx, "ty": ty, "rotacion_deg": rotacion_deg, "escala": escala}


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
        return {"inliers": 0, "desp": None, **_SIN_TRANSFORMACION}

    bf = cv2.BFMatcher(cv2.NORM_HAMMING)
    good = [m for m, n in bf.knnMatch(des1, des2, k=2) if m.distance < 0.75 * n.distance]
    if len(good) < 8:
        return {"inliers": 0, "desp": None, **_SIN_TRANSFORMACION}

    p1 = np.float32([kp1[m.queryIdx].pt for m in good])
    p2 = np.float32([kp2[m.trainIdx].pt for m in good])
    H, inlier_mask = cv2.findHomography(p1, p2, cv2.RANSAC, 5.0)
    if H is None:
        return {"inliers": 0, "desp": None, **_SIN_TRANSFORMACION}

    inlier_mask = inlier_mask.ravel().astype(bool)
    if inlier_mask.sum() == 0:
        return {"inliers": 0, "desp": None, **_SIN_TRANSFORMACION}
    p1_in, p2_in = p1[inlier_mask], p2[inlier_mask]
    disp = np.linalg.norm(p1_in - p2_in, axis=1)
    return {
        "inliers": int(inlier_mask.sum()), "desp": float(np.mean(disp)),
        **_descomponer_transformacion(p1_in, p2_in),
    }


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


def _nitidez(img: np.ndarray, mask: np.ndarray) -> float:
    """Varianza del Laplaciano -- métrica estándar de nitidez/enfoque: entre más borrosa la
    imagen, menos bordes marcados y menor la varianza. Rellena las esquinas tapadas con el gris
    promedio del resto de la imagen (no con negro) para no inyectar un borde falso que infle la
    medición -- mismo criterio que `_fase_correlate`."""
    gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    media = gris[mask == 1].mean() if (mask == 1).any() else gris.mean()
    gris[mask == 0] = media
    return float(cv2.Laplacian(gris, cv2.CV_32F).var())


def evaluar_nitidez(cliente: str, planta: str, servidor: str, camara: str, actual: np.ndarray) -> dict:
    """Compara la nitidez de hoy contra la línea base (mediana + MAD) de las últimas
    `N_DIAS_MEDIANA_BASE` imágenes del historial de esta cámara (mismo historial de
    `construir_base_por_mediana` -- no hace falta guardar nada aparte).

    Detecta lente sucio/desenfocado, una falla que ni la geometría (ORB/fase) ni la diferencia de
    contenido cubren. Usa la MAD (desviación absoluta mediana) en vez de desviación estándar
    porque es robusta a que algún día del historial ya haya sido borroso -- no se deja arrastrar
    por un par de valores extremos como sí le pasaría al promedio/desviación estándar clásicos.

    `nitidez_sospechosa` sale en `None` (no `False`) si todavía no hay las `N_DIAS_MEDIANA_BASE`
    completas, o alguna no se pudo leer o tiene otra resolución -- no es un "no, está bien", es
    "no se pudo evaluar todavía".
    """
    vacio = {"nitidez_hoy": None, "nitidez_mediana_hist": None, "nitidez_mad_hist": None,
             "nitidez_sospechosa": None}

    carpeta = _historial_dir(cliente, planta, servidor, camara)
    archivos = sorted(carpeta.glob("*.jpg")) if carpeta.exists() else []
    if len(archivos) < N_DIAS_MEDIANA_BASE:
        return vacio

    mask = _mascara_esquinas(actual.shape)
    nitidez_hoy = _nitidez(actual, mask)

    historicas = []
    for p in archivos[-N_DIAS_MEDIANA_BASE:]:
        img = imread_unicode(p)
        if img is None or img.shape != actual.shape:
            return {**vacio, "nitidez_hoy": nitidez_hoy}
        historicas.append(_nitidez(img, mask))

    mediana = float(np.median(historicas))
    mad = float(np.median(np.abs(np.array(historicas) - mediana)))

    if mad == 0:
        sospechosa = nitidez_hoy < mediana
    else:
        z_robusto = 0.6745 * (nitidez_hoy - mediana) / mad
        sospechosa = z_robusto < -UMBRAL_MAD_NITIDEZ

    return {"nitidez_hoy": nitidez_hoy, "nitidez_mediana_hist": mediana,
            "nitidez_mad_hist": mad, "nitidez_sospechosa": sospechosa}


def evaluar_salud_imagen(actual: np.ndarray) -> dict:
    """Salud absoluta de la imagen de hoy, sin comparar contra nada -- detecta una obstrucción
    total del lente (algo puesto directamente encima) de forma directa e inmediata, a diferencia
    de `evaluar_nitidez` (necesita 10 días de historial) o `_diff_contenido` (necesita una base).
    Funciona desde el primer día de una cámara nueva.

    Umbrales absolutos (0-255 en escala de grises), validados el 26/10/2026 contra las 217 cámaras
    reales de producción -- el peor caso legítimo encontrado fue varianza 32.4 / brillo 26.6
    (escena nocturna de poca textura), y una obstrucción total simulada dio varianza ~1.9. No
    detecta desenfoque gradual (una imagen empañada pero no plana sigue teniendo varianza alta) --
    para eso está `evaluar_nitidez`, son señales complementarias, no una reemplaza a la otra.
    """
    mask = _mascara_esquinas(actual.shape)
    gris = cv2.cvtColor(actual, cv2.COLOR_BGR2GRAY)
    pixeles = gris[mask == 1] if (mask == 1).any() else gris.ravel()
    varianza = float(pixeles.var())
    brillo = float(pixeles.mean())
    sospechosa = (
        varianza < UMBRAL_VARIANZA_MINIMA
        or brillo < UMBRAL_BRILLO_MINIMO
        or brillo > UMBRAL_BRILLO_MAXIMO
    )
    return {"salud_varianza": varianza, "salud_brillo": brillo, "salud_sospechosa": sospechosa}


def evaluar_par(base: np.ndarray, actual: np.ndarray, calibrado_px: float | None = None) -> dict:
    """Decide el estado geométrico de un par (base, actual) ya cargados.

    `calibrado_px` -- ver `umbral_para()`: `None` usa el umbral global para todas las cámaras.

    status: "OK" | "REVISAR" | "NO CONCLUYENTE" | "RESOLUCION DISTINTA"
    """
    if base.shape != actual.shape:
        return {"status": "RESOLUCION DISTINTA", "motivo": "resoluciones distintas",
                "orb_inliers": None, "orb_desp": None, "fase_desp": None, "fase_conf": None,
                "contenido_mean": None, "contenido_p95": None,
                "orb_tx": None, "orb_ty": None, "orb_rotacion_deg": None, "orb_escala": None}

    mask = _mascara_esquinas(base.shape)
    ancho = base.shape[1]
    umbral_px = umbral_para(ancho, calibrado_px)

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
        "orb_tx": orb["tx"], "orb_ty": orb["ty"],
        "orb_rotacion_deg": orb["rotacion_deg"], "orb_escala": orb["escala"],
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
    return imread_unicode(path)


def save_base(cliente: str, planta: str, servidor: str, camara: str, jpg_path: Path) -> None:
    path = base_path(cliente, planta, servidor, camara)
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(jpg_path, path)


# ---------------------------------------------------------------------------
# Historial de imágenes (paso 1 hacia la base por mediana -- ver ROADMAP.md, 26/10/2026)
# ---------------------------------------------------------------------------

def _historial_dir(cliente: str, planta: str, servidor: str, camara: str) -> Path:
    return IMAGE_HISTORY_ROOT / cliente / planta / servidor / camara


def historial_path(cliente: str, planta: str, servidor: str, camara: str, fecha: date) -> Path:
    return _historial_dir(cliente, planta, servidor, camara) / f"{fecha.isoformat()}.jpg"


def guardar_historial_imagen(
    cliente: str, planta: str, servidor: str, camara: str, jpg_path: Path, fecha: date,
) -> None:
    """Guarda una copia fechada del `.jpg` de hoy, para construir más adelante una base por
    mediana de los últimos `N_DIAS_MEDIANA_BASE` días en vez de la foto de un solo día.

    Mantiene una ventana rotatoria: conserva las `N_DIAS_MEDIANA_BASE` fotos más recientes y
    borra el resto -- por muestras guardadas, no por fecha de calendario, para no castigar a una
    cámara con huecos (fin de semana, falla de descarga, etc.).
    """
    destino = historial_path(cliente, planta, servidor, camara, fecha)
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(jpg_path, destino)

    archivos = sorted(destino.parent.glob("*.jpg"))
    for viejo in archivos[:-N_DIAS_MEDIANA_BASE]:
        viejo.unlink()


def fechas_en_historial(cliente: str, planta: str, servidor: str, camara: str) -> set[date]:
    """Qué fechas ya tiene guardadas el historial de una cámara (lee los nombres de archivo, no
    hace falta llevar un índice aparte)."""
    carpeta = _historial_dir(cliente, planta, servidor, camara)
    if not carpeta.exists():
        return set()
    fechas = set()
    for p in carpeta.glob("*.jpg"):
        try:
            fechas.add(date.fromisoformat(p.stem))
        except ValueError:
            continue  # nombre inesperado -- se ignora, no se adivina
    return fechas


def limpiar_historial_imagen(cliente: str, planta: str, servidor: str, camara: str) -> None:
    """Borra el historial guardado de una cámara -- se usa al reemplazar su base a mano
    (`ui/ventana_bases.py`), para que la futura mediana no mezcle fotos de antes del arreglo con
    las de después."""
    carpeta = _historial_dir(cliente, planta, servidor, camara)
    if carpeta.exists():
        for viejo in carpeta.glob("*.jpg"):
            viejo.unlink()


def construir_base_por_mediana(cliente: str, planta: str, servidor: str, camara: str) -> np.ndarray | None:
    """Arma una base de referencia como la mediana por píxel de las `N_DIAS_MEDIANA_BASE` imágenes
    más recientes del historial (ver `guardar_historial_imagen`).

    La mediana descarta sola una minoría de imágenes "malas" (objeto en cuadro, reflejo, etc.) sin
    tener que identificarlas una por una -- por eso no se filtra nada más allá de la higiene básica
    (legible, misma resolución). Exige las `N_DIAS_MEDIANA_BASE` completas: si el historial tiene
    menos, o alguna imagen no se puede leer o tiene otra resolución, regresa `None` -- quien llama
    decide qué hacer (p. ej. seguir con la base actual mientras se completa).
    """
    carpeta = _historial_dir(cliente, planta, servidor, camara)
    archivos = sorted(carpeta.glob("*.jpg")) if carpeta.exists() else []
    if len(archivos) < N_DIAS_MEDIANA_BASE:
        return None

    imagenes = [imread_unicode(p) for p in archivos[-N_DIAS_MEDIANA_BASE:]]
    if any(img is None for img in imagenes):
        return None

    resolucion = imagenes[0].shape
    if any(img.shape != resolucion for img in imagenes):
        return None

    pila = np.stack(imagenes, axis=0)
    return np.median(pila, axis=0).astype(np.uint8)


def promover_base_a_mediana(cliente: str, planta: str, servidor: str, camara: str) -> bool:
    """Si ya hay suficiente historial, reemplaza la base actual de la cámara por la mediana.

    Regresa `True` si promovió (el llamador, `main.py`, debe entonces apagar la marca de
    "promoción pendiente" en la base de datos -- este módulo no sabe nada de eso). Regresa `False`
    si todavía no hay suficiente historial -- no es un error, solo toca esperar más días.
    """
    mediana = construir_base_por_mediana(cliente, planta, servidor, camara)
    if mediana is None:
        return False
    imwrite_unicode(base_path(cliente, planta, servidor, camara), mediana)
    return True


_SIN_DIA_ANTERIOR = {"diaanterior_status": None, "diaanterior_motivo": None,
                     "diaanterior_orb_desp": None, "diaanterior_fase_desp": None}


def evaluar_dia_anterior(
    cliente: str, planta: str, servidor: str, camara: str, actual: np.ndarray,
    calibrado_px: float | None = None,
) -> dict:
    """Compara la imagen de hoy contra la más reciente guardada en el historial -- no contra la
    base fija -- reutilizando `evaluar_par()` tal cual. Señal complementaria para escenas de poca
    textura, donde comparar contra una base de meses acumula ruido (ROADMAP.md, 26/10/2026, punto
    5). **Puramente informativa por ahora**: no cambia la decisión `OK`/`REVISAR`/`NO CONCLUYENTE`.

    "El día anterior" es la foto más reciente que ya estaba en el historial -- si hubo un hueco
    (fin de semana, falla de conexión), compara contra la última real disponible, no se salta el
    día. Debe llamarse **antes** de `guardar_historial_imagen()` guarde la foto de hoy, para que
    "la más reciente del historial" no termine siendo la de hoy mismo.

    `calibrado_px` -- ver `umbral_para()`: se reusa el mismo umbral calibrado por cámara que la
    comparación contra la base, para que las dos midan con la misma vara.
    """
    carpeta = _historial_dir(cliente, planta, servidor, camara)
    archivos = sorted(carpeta.glob("*.jpg")) if carpeta.exists() else []
    if not archivos:
        return _SIN_DIA_ANTERIOR

    anterior = imread_unicode(archivos[-1])
    if anterior is None:
        return _SIN_DIA_ANTERIOR

    resultado = evaluar_par(anterior, actual, calibrado_px)
    return {
        "diaanterior_status": resultado["status"], "diaanterior_motivo": resultado["motivo"],
        "diaanterior_orb_desp": resultado["orb_desp"], "diaanterior_fase_desp": resultado["fase_desp"],
    }


# ---------------------------------------------------------------------------
# Orquestación por cámara
# ---------------------------------------------------------------------------

def compare_camera_image(
    jpg_path: Path, cliente: str, planta: str, servidor: str, camara: str,
    base_desactualizada: bool = False, fecha: date | None = None,
    umbral_calibrado_px: float | None = None,
) -> dict:
    """Compara la imagen actual de una cámara contra su base, creándola si falta.

    `base_desactualizada` viene de `perfil_camara.estado_actual` en la base de datos (ver
    ROADMAP.md, secciones 2.8 y 3) -- este módulo ya no sabe nada de archivos marcadores, el
    llamador decide si la base está marcada antes de pedir la comparación.

    `fecha` se usa para nombrar la copia que se guarda en el historial de imágenes (ver
    `guardar_historial_imagen`) -- si no se da (p. ej. scripts viejos), simplemente no se guarda
    historial para esa llamada.

    `umbral_calibrado_px` -- ver `umbral_para()`: el p95 de desplazamiento "normal" de esta cámara
    en particular (`perfil_camara.p95_desplazamiento`), si ya hay suficiente historial calibrado.
    Este módulo no sabe nada de la base de datos -- el llamador (`main.py`) decide el valor.

    status: "BASE CREADA" | "OK" | "REVISAR" | "NO CONCLUYENTE" | "RESOLUCION DISTINTA"
            | "BASE DESACTUALIZADA"
    """
    sin_geometria = {"orb_inliers": None, "orb_desp": None, "fase_desp": None, "fase_conf": None,
                      "contenido_mean": None, "contenido_p95": None,
                      "orb_tx": None, "orb_ty": None, "orb_rotacion_deg": None, "orb_escala": None}
    sin_nitidez = {"nitidez_hoy": None, "nitidez_mediana_hist": None, "nitidez_mad_hist": None,
                   "nitidez_sospechosa": None}
    sin_salud = {"salud_varianza": None, "salud_brillo": None, "salud_sospechosa": None}

    actual = imread_unicode(jpg_path)

    # Debe calcularse ANTES de guardar el historial de hoy -- si no, "la más reciente del
    # historial" sería la foto de hoy mismo, no la de ayer (ver `evaluar_dia_anterior`).
    dia_anterior = (
        evaluar_dia_anterior(cliente, planta, servidor, camara, actual, umbral_calibrado_px)
        if actual is not None else _SIN_DIA_ANTERIOR
    )

    if actual is not None and fecha is not None:
        guardar_historial_imagen(cliente, planta, servidor, camara, jpg_path, fecha)

    # Salud absoluta: no depende de base ni historial, así que se calcula siempre que la imagen se
    # pudo leer, incluso en BASE CREADA/BASE DESACTUALIZADA -- ver `evaluar_salud_imagen`.
    salud = evaluar_salud_imagen(actual) if actual is not None else sin_salud

    base = load_base(cliente, planta, servidor, camara)
    if base is None:
        save_base(cliente, planta, servidor, camara, jpg_path)
        return {"status": "BASE CREADA", "motivo": None,
                **sin_geometria, **sin_nitidez, **salud, **dia_anterior}

    if base_desactualizada:
        return {"status": "BASE DESACTUALIZADA",
                "motivo": "pendiente de que alguien suba una imagen limpia (ventana_bases.py)",
                **sin_geometria, **sin_nitidez, **salud, **dia_anterior}

    if actual is None:
        return {"status": "NO CONCLUYENTE", "motivo": "no se pudo leer la imagen",
                **sin_geometria, **sin_nitidez, **sin_salud, **_SIN_DIA_ANTERIOR}

    resultado = evaluar_par(base, actual, umbral_calibrado_px)
    resultado.update(evaluar_nitidez(cliente, planta, servidor, camara, actual))
    resultado.update(salud)
    resultado.update(dia_anterior)
    return resultado
