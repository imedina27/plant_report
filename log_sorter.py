"""Reordena los .log de revisión de plantas agrupando las líneas por cámara.

Las cámaras se procesan en paralelo al generar el log original, así que sus
líneas (IP, Puerto, Imagen IA, Imagen cámara, Configuración, Tiempo de
proceso) quedan entrelazadas entre sí. Este módulo agrupa esas líneas por
cámara y las ordena, dejando intacto el encabezado y el cierre del archivo.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

CHECK_PLANTS_ROOT = Path(os.environ["CHECK_PLANTS_ROOT"])
SORT_RULES_DIR = Path(__file__).resolve().parent / "sort_rules"

DEFAULT_SORT_CONFIG = {
    "plant_order": "alpha",
    "servidor_order": "alpha",
    "camera_order": "alpha",
}


def load_client_config(client: str) -> dict:
    """Reglas de ordenamiento para un cliente: default.json + overrides de
    sort_rules/<cliente>.json si existe."""
    config = dict(DEFAULT_SORT_CONFIG)
    for name in ("default", client):
        path = SORT_RULES_DIR / f"{name}.json"
        if path.exists():
            config.update(json.loads(path.read_text(encoding="utf-8")))
    return config


def _numeric_suffix_key(name: str) -> tuple[int, str]:
    m = re.search(r"(\d+)$", name)
    return (int(m.group(1)), name) if m else (10**9, name)


def _sort_key(name: str, order: str):
    return _numeric_suffix_key(name) if order == "numeric_suffix" else name


LOG_LINE_RE = re.compile(r"^\[(?P<time>\d{2}:\d{2}:\d{2})\]\s+(?P<level>INFO|ERROR)\s+(?P<msg>.*)$")
IP_MSG_RE = re.compile(r"^(?P<cam>\S+) IP: (?P<ip>\S+)$")
FIELD_MSG_RE = re.compile(r"^(?P<cam>\S+):\s+(?P<rest>.+)$")
ANON_ERROR_MSG_RE = re.compile(r"^\[ERROR\]\s+(?P<ip>\S+):\s+(?P<detail>.+)$")
SEPARATOR_ONLY_RE = re.compile(r"^=+$")

FIELD_ORDER = ["ip", "puerto", "imagen_ia", "imagen_camara", "configuracion", "tiempo"]


def _field_type(rest: str) -> str | None:
    if rest.startswith("Puerto "):
        return "puerto"
    if rest.startswith("Imagen IA"):
        return "imagen_ia"
    if rest.startswith("Imagen cámara"):
        return "imagen_camara"
    if rest.startswith("Configuración"):
        return "configuracion"
    if rest.startswith("Tiempo de proceso"):
        return "tiempo"
    return None


@dataclass
class CameraBlock:
    name: str
    lines: dict[str, str] = field(default_factory=dict)

    def ordered_lines(self) -> list[str]:
        return [self.lines[t] for t in FIELD_ORDER if t in self.lines]


def _is_camera_line(msg: str) -> bool:
    if IP_MSG_RE.match(msg) or ANON_ERROR_MSG_RE.match(msg):
        return True
    field_match = FIELD_MSG_RE.match(msg)
    return bool(field_match and _field_type(field_match.group("rest")))


def _parse_camera_section(lines: list[str], camera_order: str = "alpha") -> tuple[list[str], list[str]]:
    parsed: list[tuple[str, str]] = []
    unrecognized: list[str] = []
    for raw in lines:
        line = raw.rstrip("\r\n")
        if not line.strip() or SEPARATOR_ONLY_RE.match(line):
            continue
        m = LOG_LINE_RE.match(line)
        if not m:
            unrecognized.append(raw)
            continue
        parsed.append((m.group("msg"), raw))

    ip_to_camera: dict[str, str] = {}
    for msg, _raw in parsed:
        ip_match = IP_MSG_RE.match(msg)
        if ip_match:
            ip_to_camera[ip_match.group("ip")] = ip_match.group("cam")

    cameras: dict[str, CameraBlock] = {}
    for msg, raw in parsed:
        ip_match = IP_MSG_RE.match(msg)
        if ip_match:
            cam = cameras.setdefault(ip_match.group("cam"), CameraBlock(ip_match.group("cam")))
            cam.lines["ip"] = raw
            continue

        anon_err = ANON_ERROR_MSG_RE.match(msg)
        if anon_err:
            cam_name = ip_to_camera.get(anon_err.group("ip"))
            if cam_name:
                cameras.setdefault(cam_name, CameraBlock(cam_name)).lines["configuracion"] = raw
            else:
                unrecognized.append(raw)
            continue

        field_match = FIELD_MSG_RE.match(msg)
        if field_match:
            ftype = _field_type(field_match.group("rest"))
            if ftype:
                cam_name = field_match.group("cam")
                cameras.setdefault(cam_name, CameraBlock(cam_name)).lines[ftype] = raw
                continue

        unrecognized.append(raw)

    ending = "\r\n" if any(raw.endswith("\r\n") for raw in lines) else "\n"
    separator = "=" * 60 + ending

    ordered: list[str] = []
    for name in sorted(cameras, key=lambda n: _sort_key(n, camera_order)):
        ordered.extend(cameras[name].ordered_lines())
        ordered.append(separator)

    return ordered, unrecognized


def _camera_line_mask(lines: list[str]) -> list[bool]:
    raw_mask: list[bool] = []
    is_sep: list[bool] = []
    for raw in lines:
        stripped = raw.rstrip("\r\n")
        if SEPARATOR_ONLY_RE.match(stripped):
            raw_mask.append(False)
            is_sep.append(True)
            continue
        m = LOG_LINE_RE.match(stripped)
        raw_mask.append(bool(m and _is_camera_line(m.group("msg"))))
        is_sep.append(False)

    # A bare "====" separator only counts as part of a camera run when it sits
    # strictly between two real camera lines (i.e. one we added on a previous
    # sort). Otherwise it belongs to unrelated content (e.g. resumen_*.log's
    # own dividers) and must be left untouched.
    mask = list(raw_mask)
    n = len(lines)
    for i in range(n):
        if not is_sep[i]:
            continue
        before = next((k for k in range(i - 1, -1, -1) if lines[k].strip()), None)
        after = next((k for k in range(i + 1, n) if lines[k].strip()), None)
        if (before is not None and raw_mask[before]) or (after is not None and raw_mask[after]):
            mask[i] = True
    return mask


def sort_log_text(text: str, camera_order: str = "alpha") -> str:
    """Reordena cada ronda de revisión de cámaras del log de forma independiente.

    Un .log puede contener más de una ronda (una por puerto/zona escaneado),
    cada una con su propio encabezado 'YAML Read successful' y cierre '===='.
    Todo lo que no sea una línea de cámara (encabezados, separadores, líneas
    en blanco) se deja intacto en su posición original.
    """
    lines = text.splitlines(keepends=True)
    mask = _camera_line_mask(lines)

    result_lines: list[str] = []
    i, n = 0, len(lines)
    while i < n:
        if not mask[i]:
            result_lines.append(lines[i])
            i += 1
            continue
        j = i
        while j < n and mask[j]:
            j += 1
        ordered, unrecognized = _parse_camera_section(lines[i:j], camera_order)
        if unrecognized:
            print(f"  Aviso: {len(unrecognized)} línea(s) sin reconocer se conservaron al final de una ronda de cámaras.")
        result_lines.extend(ordered)
        result_lines.extend(unrecognized)
        i = j

    return "".join(l if l.endswith("\n") else l + "\n" for l in result_lines)


RESUMEN_DETAIL_HEADING = "DETALLE POR PLANTA - CÁMARAS CON FALLAS"
RESUMEN_ENTRY_RE = re.compile(r"^\s*-\s*\[(?P<servidor>[^\]]+)\]\s+(?P<alias>\S+)\s+\S+\s+(?P<campo>.+)$")
RESUMEN_PLANT_HEADER_RE = re.compile(r"^(?P<planta>\S[^:]*):$")


def sort_resumen_text(text: str, plant_order: str = "alpha", servidor_order: str = "alpha") -> str:
    """Reordena la sección 'DETALLE POR PLANTA - CÁMARAS CON FALLAS' del resumen.

    Agrupa por planta y, dentro de cada planta, por servidor (separados por
    '====' cuando hay más de uno); dentro de cada servidor, las fallas quedan
    agrupadas por campo (Puerto 80, Imagen IA, Imagen cámara, Configuración,
    Tiempo de proceso) y ordenadas alfabéticamente por alias de cámara.

    plant_order:
      - "alpha": los bloques de planta van alfabéticos por nombre de planta.
      - "lowest_server_number": van ordenados por el número más bajo de
        servidor que contengan (caso especial de AbInBev).
    servidor_order:
      - "alpha": servidores en orden alfabético por su nombre completo.
      - "numeric_suffix": por el número al final del nombre del servidor,
        ignorando el prefijo (ej. QBYMSPROD07 antes que QLYMSPROD01).

    Todo lo anterior al encabezado de esta sección se deja intacto.
    """
    lines = text.splitlines(keepends=True)
    heading_idx = next(
        (i for i, l in enumerate(lines) if l.rstrip("\r\n") == RESUMEN_DETAIL_HEADING), None
    )
    if heading_idx is None:
        return text

    head = lines[: heading_idx + 1]
    body = lines[heading_idx + 1 :]
    ending = "\r\n" if any(raw.endswith("\r\n") for raw in lines) else "\n"

    current_planta: str | None = None
    server_planta: dict[str, str] = {}
    server_entries: dict[str, list[str]] = {}
    for raw in body:
        stripped = raw.rstrip("\r\n")
        if not stripped.strip():
            continue
        entry_match = RESUMEN_ENTRY_RE.match(stripped)
        if entry_match:
            servidor = entry_match.group("servidor")
            server_planta.setdefault(servidor, current_planta or servidor)
            server_entries.setdefault(servidor, []).append(raw)
            continue
        plant_match = RESUMEN_PLANT_HEADER_RE.match(stripped)
        if plant_match:
            current_planta = plant_match.group("planta")

    if not server_entries:
        return text

    separator = "=" * 42 + ending

    planta_servers: dict[str, list[str]] = {}
    for servidor, planta in server_planta.items():
        planta_servers.setdefault(planta, []).append(servidor)
    for servers in planta_servers.values():
        servers.sort(key=lambda s: _sort_key(s, servidor_order))

    if plant_order == "lowest_server_number":
        planta_key = lambda planta: min(_numeric_suffix_key(s) for s in planta_servers[planta])
    else:
        planta_key = lambda planta: planta
    ordered_plantas = sorted(planta_servers, key=planta_key)

    out: list[str] = list(head)
    for idx, planta in enumerate(ordered_plantas):
        if idx > 0:
            out.append(ending)
        out.append(f"{planta}:{ending}")

        for s_idx, servidor in enumerate(planta_servers[planta]):
            if s_idx > 0:
                out.append(separator)

            by_field: dict[str, list[tuple[str, str]]] = {}
            for raw in server_entries[servidor]:
                m = RESUMEN_ENTRY_RE.match(raw.rstrip("\r\n"))
                ftype = _field_type(m.group("campo")) or "otro"
                by_field.setdefault(ftype, []).append((m.group("alias"), raw))

            for ftype in [*FIELD_ORDER, "otro"]:
                for _alias, raw in sorted(by_field.get(ftype, []), key=lambda t: t[0]):
                    out.append(raw)

    return "".join(l if l.endswith(("\n", "\r\n")) else l + ending for l in out)


def sort_log_file(path: Path, config: dict | None = None) -> bool:
    """Reordena un .log en su lugar. Devuelve True si el contenido cambió."""
    config = config or DEFAULT_SORT_CONFIG
    original = path.read_text(encoding="utf-8", newline="")
    if path.name.startswith("resumen_"):
        sorted_text = sort_resumen_text(
            original,
            plant_order=config["plant_order"],
            servidor_order=config["servidor_order"],
        )
    else:
        sorted_text = sort_log_text(original, camera_order=config["camera_order"])
    if sorted_text == original:
        return False
    backup_path = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, backup_path)
    path.write_text(sorted_text, encoding="utf-8", newline="")
    return True


def sort_logs_for_date(date_str: str, root: Path = CHECK_PLANTS_ROOT) -> None:
    log_paths = sorted(root.glob(f"*/*/{date_str}/**/*.log"))
    if not log_paths:
        print(f"No se encontraron archivos .log para la fecha {date_str} en {root}")
        return

    print(f"Encontrados {len(log_paths)} archivo(s) .log para la fecha {date_str}.")
    config_cache: dict[str, dict] = {}
    for log_path in log_paths:
        client = log_path.relative_to(root).parts[0]
        config = config_cache.setdefault(client, load_client_config(client))
        changed = sort_log_file(log_path, config)
        status = "ordenado" if changed else "sin cambios"
        print(f"  - {log_path.relative_to(root)}: {status}")
