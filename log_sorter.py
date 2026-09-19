"""Reordena los .log de revisión de plantas agrupando las líneas por cámara.

Las cámaras se procesan en paralelo al generar el log original, así que sus
líneas (IP, Puerto, Imagen IA, Imagen cámara, Configuración, Tiempo de
proceso) quedan entrelazadas entre sí. Este módulo agrupa esas líneas por
cámara y las ordena, dejando intacto el encabezado y el cierre del archivo.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

CHECK_PLANTS_ROOT = Path(r"D:\Imágenes\Quantum Labs\Check Plants")

LOG_LINE_RE = re.compile(r"^\[(?P<time>\d{2}:\d{2}:\d{2})\]\s+(?P<level>INFO|ERROR)\s+(?P<msg>.*)$")
IP_MSG_RE = re.compile(r"^(?P<cam>\S+) IP: (?P<ip>\S+)$")
FIELD_MSG_RE = re.compile(r"^(?P<cam>\S+):\s+(?P<rest>.+)$")
ANON_ERROR_MSG_RE = re.compile(r"^\[ERROR\]\s+(?P<ip>\S+):\s+(?P<detail>.+)$")

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


def _parse_camera_section(lines: list[str]) -> tuple[list[str], list[str]]:
    parsed: list[tuple[str, str]] = []
    unrecognized: list[str] = []
    for raw in lines:
        line = raw.rstrip("\r\n")
        if not line.strip():
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
    for name in sorted(cameras):
        ordered.extend(cameras[name].ordered_lines())
        ordered.append(separator)

    return ordered, unrecognized


def _camera_line_mask(lines: list[str]) -> list[bool]:
    mask = []
    for raw in lines:
        m = LOG_LINE_RE.match(raw.rstrip("\r\n"))
        mask.append(bool(m and _is_camera_line(m.group("msg"))))
    return mask


def sort_log_text(text: str) -> str:
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
        ordered, unrecognized = _parse_camera_section(lines[i:j])
        if unrecognized:
            print(f"  Aviso: {len(unrecognized)} línea(s) sin reconocer se conservaron al final de una ronda de cámaras.")
        result_lines.extend(ordered)
        result_lines.extend(unrecognized)
        i = j

    return "".join(l if l.endswith("\n") else l + "\n" for l in result_lines)


def sort_log_file(path: Path) -> bool:
    """Reordena un .log en su lugar. Devuelve True si el contenido cambió."""
    original = path.read_text(encoding="utf-8", newline="")
    sorted_text = sort_log_text(original)
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
    for log_path in log_paths:
        changed = sort_log_file(log_path)
        status = "ordenado" if changed else "sin cambios"
        print(f"  - {log_path.relative_to(root)}: {status}")
