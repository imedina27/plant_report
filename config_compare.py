"""Compara la configuración .json de cada cámara contra una base de referencia.

La marca de la cámara se detecta leyendo el contenido de su .json (no existe un
inventario externo marca-por-cámara). Por marca se compara un subconjunto curado
de campos agrupados en 4 categorías (Imagen, Video, Compresión, Network) — ver
ROADMAP.md, Fase 1, para el detalle y el porqué de cada decisión.

La base de un servidor/cámara que no la tiene todavía se crea automáticamente
la primera vez que se procesa (copiando su .json de ese día), y de ahí en
adelante queda fija hasta que algo la actualice deliberadamente.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

CHECK_PLANTS_ROOT = Path(os.environ["CHECK_PLANTS_ROOT"])
CONFIG_BASE_ROOT = Path(os.environ["CONFIG_BASE_ROOT"])

MISSING = object()


def _get(data: dict, path: str):
    node = data
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return MISSING
        node = node[part]
    return node


# ---------------------------------------------------------------------------
# Detección de marca (por contenido del .json, ver ROADMAP.md)
# ---------------------------------------------------------------------------

def detect_brand(config: dict) -> str | None:
    if _get(config, "Brand.Brand") == "AXIS":
        return "AXIS"

    xmlns = _get(config, "DeviceInfo.@xmlns")
    if isinstance(xmlns, str) and "hikvision.com" in xmlns:
        return "HIKVISION"

    firmware = _get(config, "system.info.firmwareversion")
    if isinstance(firmware, str) and "VVTK" in firmware:
        return "VIVOTEK"

    return None


# ---------------------------------------------------------------------------
# AXIS — Image.{n}/ImageSource.{n} solo para vistas con Enabled: "yes"
# ---------------------------------------------------------------------------

_AXIS_VIEW_FIELD_TEMPLATES = {
    "imagen": [
        "Image.{n}.Appearance.ColorEnabled",
        "Image.{n}.Appearance.MirrorEnabled",
        "Image.{n}.Appearance.Resolution",
        "Image.{n}.Appearance.Rotation",
        "ImageSource.{n}.DayNight.IrCutFilter",
        "ImageSource.{n}.DayNight.ShiftLevel",
        "ImageSource.{n}.DCIris.Enabled",
        "ImageSource.{n}.DCIris.Position",
        "ImageSource.{n}.DCIris.TypeID",
        "ImageSource.{n}.Focus.Mode",
        "ImageSource.{n}.Focus.NearLimit",
        "ImageSource.{n}.Focus.Pos",
        "ImageSource.{n}.Focus.TemperatureCorrection",
        "ImageSource.{n}.Sensor.AspectRatio",
        "ImageSource.{n}.Sensor.Brightness",
        "ImageSource.{n}.Sensor.CaptureMode",
        "ImageSource.{n}.Sensor.ColorLevel",
        "ImageSource.{n}.Sensor.Contrast",
        "ImageSource.{n}.Sensor.Exposure",
        "ImageSource.{n}.Sensor.ExposurePriority",
        "ImageSource.{n}.Sensor.ExposurePriorityLowlight",
        "ImageSource.{n}.Sensor.ExposurePriorityNormal",
        "ImageSource.{n}.Sensor.ExposureValue",
        "ImageSource.{n}.Sensor.ExposureWindow",
        "ImageSource.{n}.Sensor.LocalContrast",
        "ImageSource.{n}.Sensor.ManualGain",
        "ImageSource.{n}.Sensor.ManualGainControl",
        "ImageSource.{n}.Sensor.ManualShutter",
        "ImageSource.{n}.Sensor.ManualShutterControl",
        "ImageSource.{n}.Sensor.MaxAutoGainControlLowlight",
        "ImageSource.{n}.Sensor.MaxAutoGainControlNormal",
        "ImageSource.{n}.Sensor.MaxExposureTime",
        "ImageSource.{n}.Sensor.MaxFastShutter",
        "ImageSource.{n}.Sensor.MaxGain",
        "ImageSource.{n}.Sensor.MaxSlowShutter",
        "ImageSource.{n}.Sensor.MinExposureTime",
        "ImageSource.{n}.Sensor.MinGain",
        "ImageSource.{n}.Sensor.Sharpness",
        "ImageSource.{n}.Sensor.WDR",
        "ImageSource.{n}.Sensor.WhiteBalance",
        "ImageSource.{n}.Sensor.WhiteBalanceWindow",
        "ImageSource.{n}.Sensor.WhiteBalanceXstart",
        "ImageSource.{n}.Sensor.WhiteBalanceXstop",
        "ImageSource.{n}.Sensor.WhiteBalanceYstart",
        "ImageSource.{n}.Sensor.WhiteBalanceYstop",
    ],
    "video": [
        "Image.{n}.Stream.Duration",
        "Image.{n}.Stream.FPS",
        "Image.{n}.Stream.NbrOfFrames",
        "Image.{n}.MPEG.Complexity",
        "Image.{n}.MPEG.ConfigHeaderInterval",
        "Image.{n}.MPEG.FrameSkipMode",
        "Image.{n}.MPEG.ICount",
        "Image.{n}.MPEG.PCount",
        "Image.{n}.MPEG.UserDataEnabled",
        "Image.{n}.MPEG.UserDataInterval",
        "Image.{n}.MPEG.ZChromaQPMode",
        "Image.{n}.MPEG.ZFpsMode",
        "Image.{n}.MPEG.ZGopMode",
        "Image.{n}.MPEG.ZMaxGopLength",
        "Image.{n}.MPEG.ZMinFps",
        "Image.{n}.MPEG.ZStrength",
        "Image.{n}.RateControl.Mode",
        "Image.{n}.RateControl.Priority",
    ],
    "compresion": [
        "Image.{n}.Appearance.Compression",
        "Image.{n}.MPEG.H264.Profile",
        "Image.{n}.MPEG.H264.PSEnabled",
        "Image.{n}.RateControl.MaxBitrate",
        "Image.{n}.RateControl.TargetBitrate",
        "Image.{n}.SizeControl.MaxFrameSize",
    ],
}

_AXIS_NETWORK_FIELDS = [
    "Network.IPAddress",
    "Network.SubnetMask",
    "Network.DefaultRouter",
    "Network.Broadcast",
    "Network.BootProto",
    "Network.HostName",
    "Network.DomainName",
    "Network.Media",
    "Network.DNSServer1",
    "Network.DNSServer2",
    "Network.eth0.IPAddress",
    "Network.eth0.SubnetMask",
    "Network.eth0.MACAddress",
    "Network.eth0.Broadcast",
    "Network.RTSP.Port",
    "Network.RTSP.Enabled",
    "Network.HTTP.AuthenticationPolicy",
    "Network.SSH.Enabled",
    "Network.UPnP.Enabled",
]


def _axis_enabled_views(config: dict) -> list[str]:
    image = config.get("Image")
    if not isinstance(image, dict):
        return []
    return sorted(
        key for key, val in image.items()
        if isinstance(val, dict) and val.get("Enabled") == "yes"
    )


def _axis_fields(config: dict) -> dict[str, list[str]]:
    fields: dict[str, list[str]] = {category: [] for category in _AXIS_VIEW_FIELD_TEMPLATES}
    for view in _axis_enabled_views(config):
        for category, templates in _AXIS_VIEW_FIELD_TEMPLATES.items():
            fields[category].extend(t.format(n=view) for t in templates)
    fields["network"] = list(_AXIS_NETWORK_FIELDS)
    return fields


# ---------------------------------------------------------------------------
# HIKVISION — un solo canal, sin índices que resolver
# ---------------------------------------------------------------------------

_HIKVISION_FIELDS = {
    "imagen": [
        "ImageChannel.ImageFlip.enabled",
        "ImageChannel.IrcutFilter.IrcutFilterType",
        "ImageChannel.IrcutFilter.nightToDayFilterLevel",
        "ImageChannel.IrcutFilter.nightToDayFilterTime",
        "ImageChannel.Exposure.ExposureType",
        "ImageChannel.powerLineFrequency.powerLineFrequencyMode",
        "ImageChannel.Scene.mode",
        "ImageChannel.WDR.mode",
        "ImageChannel.WDR.WDRLevel",
        "ImageChannel.BLC.enabled",
        "ImageChannel.NoiseReduce.mode",
        "ImageChannel.NoiseReduce.GeneralMode.generalLevel",
        "ImageChannel.WhiteBalance.WhiteBalanceStyle",
        "ImageChannel.WhiteBalance.WhiteBalanceRed",
        "ImageChannel.WhiteBalance.WhiteBalanceBlue",
        "ImageChannel.Sharpness.SharpnessLevel",
        "ImageChannel.Gain.GainLevel",
        "ImageChannel.Shutter.ShutterLevel",
        "ImageChannel.Color.brightnessLevel",
        "ImageChannel.Color.contrastLevel",
        "ImageChannel.Color.saturationLevel",
        "ImageChannel.Dehaze.DehazeMode",
    ],
    "video": [
        "StreamingChannel.Video.videoCodecType",
        "StreamingChannel.Video.videoScanType",
        "StreamingChannel.Video.videoResolutionWidth",
        "StreamingChannel.Video.videoResolutionHeight",
        "StreamingChannel.Video.maxFrameRate",
        "StreamingChannel.Video.GovLength",
        "StreamingChannel.Video.H264Profile",
        "StreamingChannel.Video.H265Profile",
        "StreamingChannel.Video.SVC.enabled",
        "StreamingChannel.Video.SmartCodec.enabled",
        "StreamingChannel.Video.snapShotImageType",
    ],
    "compresion": [
        "StreamingChannel.Video.videoQualityControlType",
        "StreamingChannel.Video.constantBitRate",
        "StreamingChannel.Video.fixedQuality",
        "StreamingChannel.Video.vbrUpperCap",
        "StreamingChannel.Video.vbrLowerCap",
        "StreamingChannel.Video.keyFrameInterval",
        "StreamingChannel.Video.smoothing",
    ],
    "network": [
        "NetworkInterface.IPAddress.ipAddress",
        "NetworkInterface.IPAddress.subnetMask",
        "NetworkInterface.IPAddress.addressingType",
        "NetworkInterface.IPAddress.DefaultGateway.ipAddress",
        "NetworkInterface.IPAddress.PrimaryDNS.ipAddress",
        "NetworkInterface.IPAddress.SecondaryDNS.ipAddress",
        "NetworkInterface.Link.MACAddress",
        "NetworkInterface.Link.speed",
        "NetworkInterface.Link.duplex",
        "NetworkInterface.Link.MTU",
    ],
}


def _hikvision_fields(config: dict) -> dict[str, list[str]]:
    return {category: list(paths) for category, paths in _HIKVISION_FIELDS.items()}


# ---------------------------------------------------------------------------
# VIVOTEK — videoin.c0.{s} por cada stream presente (s0, s1, s2, ...)
# ---------------------------------------------------------------------------

_VIVOTEK_STREAM_FIELD_TEMPLATES = {
    "video": [
        "videoin.c0.{s}.codectype",
        "videoin.c0.{s}.resolution",
        "videoin.c0.{s}.h264.profile",
        "videoin.c0.{s}.h264.maxframe",
        "videoin.c0.{s}.h264.prioritypolicy",
        "videoin.c0.{s}.h265.profile",
        "videoin.c0.{s}.h265.maxframe",
        "videoin.c0.{s}.h265.prioritypolicy",
        "videoin.c0.{s}.mjpeg.maxframe",
    ],
    "compresion": [
        "videoin.c0.{s}.h264.ratecontrolmode",
        "videoin.c0.{s}.h264.bitrate",
        "videoin.c0.{s}.h264.quant",
        "videoin.c0.{s}.h264.qvalue",
        "videoin.c0.{s}.h264.qpercent",
        "videoin.c0.{s}.h264.intraperiod",
        "videoin.c0.{s}.h264.maxvbrbitrate",
        "videoin.c0.{s}.h265.ratecontrolmode",
        "videoin.c0.{s}.h265.bitrate",
        "videoin.c0.{s}.h265.quant",
        "videoin.c0.{s}.h265.qvalue",
        "videoin.c0.{s}.h265.qpercent",
        "videoin.c0.{s}.h265.intraperiod",
        "videoin.c0.{s}.h265.maxvbrbitrate",
        "videoin.c0.{s}.mjpeg.ratecontrolmode",
        "videoin.c0.{s}.mjpeg.bitrate",
        "videoin.c0.{s}.mjpeg.quant",
        "videoin.c0.{s}.mjpeg.qvalue",
        "videoin.c0.{s}.mjpeg.qpercent",
    ],
}

_VIVOTEK_IMAGE_FIELDS = [
    "image.c0.brightness",
    "image.c0.brightnesspercent",
    "image.c0.saturation",
    "image.c0.saturationpercent",
    "image.c0.contrast",
    "image.c0.contrastpercent",
    "image.c0.sharpness",
    "image.c0.sharpnesspercent",
    "image.c0.gammacurve",
    "image.c0.hlm",
    "image.c0.defog.mode",
    "image.c0.defog.strength",
    "image.c0.eis.mode",
    "image.c0.eis.strength",
    "image.c0.dnr.mode",
    "image.c0.dnr.strength",
    "image.c0.scene.mode",
    "videoin.c0.whitebalance",
    "videoin.c0.exposurelevel",
    "videoin.c0.irismode",
    "videoin.c0.maxgain",
    "videoin.c0.mingain",
    "videoin.c0.color",
    "videoin.c0.flip",
    "videoin.c0.mirror",
    "videoin.c0.rotate",
    "videoin.c0.cmosfreq",
    "videoin.c0.wdrc.mode",
    "videoin.c0.wdrc.strength",
    "videoin.c0.wdrpro.mode",
    "videoin.c0.piris.mode",
    "videoin.c0.piris.position",
    "videoin.c0.aespeed.mode",
    "videoin.c0.aespeed.speedlevel",
    "videoin.c0.aespeed.sensitivity",
]

_VIVOTEK_NETWORK_FIELDS = [
    "network.ipaddress",
    "network.subnet",
    "network.router",
    "network.dns1",
    "network.dns2",
    "network.http.port",
    "network.http.alternateport",
    "network.http.authmode",
    "network.https.port",
    "network.rtsp.port",
    "network.rtsp.authmode",
    "network.pppoe.user",
    "network.ieee8021x.enable",
    "network.qos.cos.enable",
    "network.qos.dscp.enable",
]

_STREAM_RE = re.compile(r"s\d+")


def _vivotek_streams(config: dict) -> list[str]:
    videoin_c0 = _get(config, "videoin.c0")
    if not isinstance(videoin_c0, dict):
        return []
    return sorted(k for k in videoin_c0 if _STREAM_RE.fullmatch(k))


def _vivotek_fields(config: dict) -> dict[str, list[str]]:
    fields: dict[str, list[str]] = {
        "imagen": list(_VIVOTEK_IMAGE_FIELDS),
        "network": list(_VIVOTEK_NETWORK_FIELDS),
        "video": [],
        "compresion": [],
    }
    for stream in _vivotek_streams(config):
        for category, templates in _VIVOTEK_STREAM_FIELD_TEMPLATES.items():
            fields[category].extend(t.format(s=stream) for t in templates)
    return fields


_FIELD_RESOLVERS = {
    "AXIS": _axis_fields,
    "HIKVISION": _hikvision_fields,
    "VIVOTEK": _vivotek_fields,
}


def fields_for(brand: str, config: dict) -> dict[str, list[str]]:
    resolver = _FIELD_RESOLVERS.get(brand)
    if resolver is None:
        raise ValueError(f"Marca sin soporte de comparación: {brand}")
    return resolver(config)


# ---------------------------------------------------------------------------
# Comparación
# ---------------------------------------------------------------------------

def compare(current: dict, base: dict, brand: str) -> list[dict]:
    """Compara current vs. base para los campos curados de esa marca.

    Coincidencia exacta de texto por campo. Si un campo no existe en el
    dump actual o en la base, se ignora (no se considera diferencia).
    """
    diffs = []
    for category, paths in fields_for(brand, current).items():
        for path in paths:
            cur_val = _get(current, path)
            base_val = _get(base, path)
            if cur_val is MISSING or base_val is MISSING:
                continue
            if cur_val != base_val:
                diffs.append(
                    {"categoria": category, "campo": path, "base": base_val, "actual": cur_val}
                )
    return diffs


# ---------------------------------------------------------------------------
# Base de referencia
# ---------------------------------------------------------------------------

def base_path(cliente: str, planta: str, servidor: str, camara: str) -> Path:
    return CONFIG_BASE_ROOT / cliente / planta / servidor / f"{camara}.json"


def load_base(cliente: str, planta: str, servidor: str, camara: str) -> dict | None:
    path = base_path(cliente, planta, servidor, camara)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_base(cliente: str, planta: str, servidor: str, camara: str, config: dict) -> None:
    path = base_path(cliente, planta, servidor, camara)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=4, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Orquestación por cámara
# ---------------------------------------------------------------------------

def compare_camera_config(json_path: Path, cliente: str, planta: str, servidor: str, camara: str) -> dict:
    """Compara el .json actual de una cámara contra su base, creándola si falta.

    status: "MARCA NO SOPORTADA" | "BASE CREADA" | "OK" | "CAMBIO"
    """
    current = json.loads(json_path.read_text(encoding="utf-8"))

    brand = detect_brand(current)
    if brand is None:
        return {"status": "MARCA NO SOPORTADA", "marca": None, "diferencias": []}

    base = load_base(cliente, planta, servidor, camara)
    if base is None:
        save_base(cliente, planta, servidor, camara, current)
        return {"status": "BASE CREADA", "marca": brand, "diferencias": []}

    diffs = compare(current, base, brand)
    return {"status": "CAMBIO" if diffs else "OK", "marca": brand, "diferencias": diffs}
