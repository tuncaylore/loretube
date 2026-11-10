"""Uygulama yapilandirmasi ve calisma dizinleri."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def find_ffmpeg() -> str | None:
    override = os.getenv("TUBEFLOW_FFMPEG")
    if override:
        candidate = Path(override)
        if candidate.is_file():
            return str(candidate)
        if candidate.is_dir():
            exe = candidate / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
            if exe.is_file():
                return str(exe)
    local = BASE_DIR / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe"
    if local.is_file():
        return str(local)
    return shutil.which("ffmpeg")


class Config:
    def __init__(self) -> None:
        self.base_dir = BASE_DIR
        self.download_dir = Path(
            os.getenv("TUBEFLOW_DOWNLOAD_DIR", str(BASE_DIR / "downloads"))
        ).resolve()
        self.data_dir = Path(
            os.getenv("TUBEFLOW_DATA_DIR", str(BASE_DIR / "data"))
        ).resolve()
        self.history_file = self.data_dir / "history.json"
        self.template_dir = BASE_DIR / "templates"
        self.static_dir = BASE_DIR / "static"

        self.host = "127.0.0.1"
        self.port = _env_int("TUBEFLOW_PORT", 5000)
        self.lan_port = _env_int("TUBEFLOW_LAN_PORT", 5001)
        self.token_ttl = max(300, _env_int("TUBEFLOW_TOKEN_TTL", 86400))
        self.retention_days = max(1, _env_int("TUBEFLOW_RETENTION_DAYS", 7))
        self.max_history = max(1, _env_int("TUBEFLOW_MAX_HISTORY", 50))
        self.max_concurrent = max(1, _env_int("TUBEFLOW_MAX_CONCURRENT", 2))
        self.lan_ip_override = os.getenv("TUBEFLOW_LAN_IP")
        self.ffmpeg_path = find_ffmpeg()
        self.no_browser = os.getenv("TUBEFLOW_NO_BROWSER") == "1"

        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
