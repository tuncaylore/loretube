"""Download and verify the Windows essentials FFmpeg build into tools/."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
BIN_DIR = BASE_DIR / "tools" / "ffmpeg" / "bin"
FFMPEG_EXE = BIN_DIR / "ffmpeg.exe"
BASE_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
CHECKSUM_URL = BASE_URL + ".sha256"
MAX_DOWNLOAD_BYTES = 160 * 1024 * 1024
MAX_EXECUTABLE_BYTES = 250 * 1024 * 1024


def _download(url: str, destination: Path, limit: int | None = None) -> None:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "LoreFlow-FFmpeg-Setup/1.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response, destination.open("wb") as output:
        length = response.headers.get("Content-Length")
        if limit is not None and length and int(length) > limit:
            raise RuntimeError("Sunucudan beklenenden büyük bir indirme yanıtı alındı.")
        total = 0
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if limit is not None and total > limit:
                raise RuntimeError("İndirilen dosya izin verilen boyutu aştı.")
            output.write(chunk)


def _expected_sha256(value: str) -> str:
    match = re.search(r"\b([a-fA-F0-9]{64})\b", value)
    if not match:
        raise RuntimeError("FFmpeg checksum dosyası okunamadı.")
    return match.group(1).lower()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def install() -> bool:
    if os.name != "nt":
        print("FFmpeg otomatik kurulumu yalnızca Windows'ta destekleniyor.")
        return False
    configured = os.environ.get("TUBEFLOW_FFMPEG")
    if configured:
        configured_path = Path(configured)
        if configured_path.is_dir():
            configured_path /= "ffmpeg.exe"
        if configured_path.is_file():
            print(f"Yapılandırılmış FFmpeg bulundu: {configured_path}")
            return True
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        print(f"Sistemdeki FFmpeg bulundu: {system_ffmpeg}")
        return True
    if FFMPEG_EXE.is_file():
        print(f"Proje içindeki FFmpeg zaten kurulu: {FFMPEG_EXE}")
        return True

    print("FFmpeg bulunamadı; güvenilir Windows paketi indiriliyor (yaklaşık 110 MB)...")
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="loreflow-ffmpeg-") as temporary:
        temp_dir = Path(temporary)
        archive = temp_dir / "ffmpeg.zip"
        checksum_file = temp_dir / "ffmpeg.zip.sha256"
        try:
            _download(CHECKSUM_URL, checksum_file, 4096)
            expected = _expected_sha256(checksum_file.read_text(encoding="utf-8"))
            _download(BASE_URL, archive, MAX_DOWNLOAD_BYTES)
        except (OSError, urllib.error.URLError, TimeoutError, ValueError, RuntimeError) as exc:
            raise RuntimeError(f"FFmpeg indirilemedi: {exc}") from exc

        actual = _sha256(archive)
        if actual != expected:
            raise RuntimeError("FFmpeg arşivinin SHA-256 doğrulaması başarısız oldu.")
        print("İndirme doğrulandı; FFmpeg bileşenleri kuruluyor...")

        try:
            with zipfile.ZipFile(archive) as package:
                ffmpeg_member = next(
                    (name for name in package.namelist() if name.lower().endswith("/bin/ffmpeg.exe")),
                    None,
                )
                ffprobe_member = next(
                    (name for name in package.namelist() if name.lower().endswith("/bin/ffprobe.exe")),
                    None,
                )
                if not ffmpeg_member:
                    raise RuntimeError("Arşivde ffmpeg.exe bulunamadı.")
                for member, output in (
                    (ffmpeg_member, FFMPEG_EXE),
                    (ffprobe_member, BIN_DIR / "ffprobe.exe" if ffprobe_member else None),
                ):
                    if member is None or output is None:
                        continue
                    info = package.getinfo(member)
                    if info.file_size > MAX_EXECUTABLE_BYTES:
                        raise RuntimeError("Arşivde beklenmeyen boyutta bir çalıştırılabilir dosya var.")
                    temporary_output = output.with_suffix(output.suffix + ".tmp")
                    with package.open(member) as source, temporary_output.open("wb") as target:
                        shutil.copyfileobj(source, target)
                    temporary_output.replace(output)
        except (OSError, zipfile.BadZipFile, KeyError) as exc:
            FFMPEG_EXE.unlink(missing_ok=True)
            raise RuntimeError(f"FFmpeg arşivi açılamadı: {exc}") from exc

    print(f"FFmpeg kuruldu: {FFMPEG_EXE}")
    return True


if __name__ == "__main__":
    try:
        sys.exit(0 if install() else 1)
    except Exception as exc:  # setup failures are shown plainly before app start
        print(f"[UYARI] {exc}")
        print("LoreFlow FFmpeg olmadan açılacak; MP3 dönüşümü kullanılamayabilir.")
        sys.exit(1)
