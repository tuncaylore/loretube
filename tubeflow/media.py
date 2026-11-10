"""yt-dlp ile video bilgisi alma, format haritalama ve Turkce hata cevirisi."""

from __future__ import annotations

import re
from typing import Any

import yt_dlp

from .config import Config

_FORMAT_LABELS = {
    144: "144p",
    240: "240p",
    360: "360p",
    480: "480p",
    720: "720p",
    1080: "1080p",
    1440: "1440p",
    2160: "2160p",
    4320: "4320p",
}
_AUDIO_QUALITY_STEPS = (320, 192, 128)


class MediaError(Exception):
    """Kullaniciya gosterilecek medya hatasi."""


def translate_error(message: str) -> str:
    text = (message or "").lower()
    if "ffmpeg" in text and any(
        key in text for key in ("not found", "not installed", "not available", "not recognized")
    ):
        return (
            "FFmpeg bulunamadı. MP3 dönüşümü ve video birleştirme için FFmpeg gerekir. "
            "Uygulamayı run.bat ile yeniden başlatıp FFmpeg kurulumunu kontrol edin."
        )
    if "ffmpeg" in text or "postprocess" in text or "post-processing" in text:
        return (
            "FFmpeg video/ses dosyasını işlerken hata verdi. FFmpeg kurulumunu ve boş disk alanını "
            "kontrol edip yeniden deneyin."
        )
    if "requested format is not available" in text or "requested format not available" in text:
        return "Seçilen kalite şu anda YouTube tarafından sunulmuyor. Bağlantıyı yeniden inceleyip başka bir kalite seçin."
    if "private video" in text or "this video is private" in text:
        return "Bu video ozel. Ozel veya uyelik gerektiren videolar desteklenmiyor."
    if "sign in" in text or "login" in text or "authentication" in text or "cookies" in text:
        return "Bu icerik oturum acmayi gerektiriyor. Uyelik gerektiren icerikler desteklenmiyor."
    if "age" in text and ("confirm" in text or "restricted" in text):
        return "Bu video yas siniri nedeniyle erisilemiyor."
    if "429" in text or "too many requests" in text:
        return "YouTube cok fazla istek algiladi. Biraz bekleyip yeniden deneyin."
    if "unsupported url" in text:
        return "Bu baglanti desteklenmiyor. Gecerli bir YouTube video adresi kullanin."
    if "not available" in text or "unavailable" in text or "removed" in text or "does not exist" in text:
        return "Video bulunamadi. Kaldirilmis veya erisime kapatilmis olabilir."
    if "geo" in text or "country" in text or "region" in text:
        return "Bu video bulundugunuz bolgede erisilemiyor."
    if "copyright" in text:
        return "Bu video telif nedeniyle erisilemiyor."
    if any(
        key in text
        for key in (
            "timed out",
            "timeout",
            "connection",
            "network",
            "getaddrinfo",
            "ssl",
            "temporary failure",
            "name or service",
        )
    ):
        return "Ag baglantisi kurulamadi. Internet baglantisinizi kontrol edip yeniden deneyin."
    if "disk" in text or "no space" in text:
        return "Yeterli disk alani yok. Yer acip yeniden deneyin."
    return "Islem tamamlanamadi. Baglantiyi kontrol edip yeniden deneyin."


def format_duration(seconds: int | float | None) -> str:
    if not seconds:
        return ""
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _pick_thumbnail(info: dict[str, Any]) -> str:
    thumbnails = info.get("thumbnails") or []
    best_url = ""
    best_width = -1
    for thumb in thumbnails:
        url = thumb.get("url")
        width = int(thumb.get("width") or 0)
        if isinstance(url, str) and url.startswith(("http://", "https://")) and width >= best_width:
            best_url = url
            best_width = width
    if best_url:
        return best_url
    direct = info.get("thumbnail")
    if isinstance(direct, str) and direct.startswith(("http://", "https://")):
        return direct
    return ""


def _video_qualities(formats: list[dict[str, Any]]) -> list[dict[str, Any]]:
    heights: set[int] = set()
    for fmt in formats:
        height = fmt.get("height")
        if not height:
            continue
        if fmt.get("vcodec") in (None, "none"):
            continue
        try:
            heights.add(int(height))
        except (TypeError, ValueError):
            continue
    qualities = []
    for height in sorted(heights):
        if height < 144 or height > 4320:
            continue
        label = _FORMAT_LABELS.get(height, f"{height}p")
        qualities.append({"value": str(height), "label": label, "height": height})
    return qualities


def _audio_qualities(formats: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bitrates: set[int] = set()
    for fmt in formats:
        if fmt.get("vcodec") not in (None, "none"):
            continue
        abr = fmt.get("abr")
        if not abr:
            continue
        try:
            value = int(round(float(abr)))
        except (TypeError, ValueError):
            continue
        if 24 <= value <= 512:
            bitrates.add(value)
    ordered = sorted(bitrates, reverse=True)[:6]
    qualities = [{"value": str(value), "label": f"{value} kbps"} for value in ordered]
    if not qualities:
        qualities = [{"value": "best", "label": "En iyi ses"}]
    return qualities


def _has_audio(formats: list[dict[str, Any]]) -> bool:
    return any(fmt.get("acodec") not in (None, "none") for fmt in formats)


def build_metadata(info: dict[str, Any], canonical_url: str, cfg: Config) -> dict[str, Any]:
    formats = info.get("formats") or []
    if not isinstance(formats, list):
        formats = []
    has_audio = _has_audio(formats)
    video_qualities = _video_qualities(formats)
    audio_qualities = _audio_qualities(formats)
    ffmpeg_ready = bool(cfg.ffmpeg_path)

    mp3_qualities = (
        [{"value": str(value), "label": f"{value} kbps"} for value in _AUDIO_QUALITY_STEPS]
        if has_audio and ffmpeg_ready
        else []
    )

    video_section = {
        "available": bool(video_qualities),
        "reason": "" if video_qualities else "Bu videoda indirilebilir bir goruntu formati yok.",
        "qualities": video_qualities,
    }
    audio_section = {
        "available": has_audio,
        "reason": "" if has_audio else "Bu videoda ses akisi bulunmuyor.",
        "qualities": audio_qualities if has_audio else [],
    }
    if has_audio and not ffmpeg_ready:
        mp3_reason = "MP3 icin FFmpeg gerekir; FFmpeg bulunamadi."
    elif not has_audio:
        mp3_reason = "Bu videoda ses akisi bulunmuyor."
    else:
        mp3_reason = ""
    mp3_section = {
        "available": bool(mp3_qualities),
        "reason": mp3_reason,
        "qualities": mp3_qualities,
    }

    title = info.get("title") or "Bilinmeyen video"
    uploader = info.get("uploader") or info.get("channel") or ""
    duration = info.get("duration")

    return {
        "url": canonical_url,
        "id": info.get("id") or "",
        "title": title,
        "thumbnail": _pick_thumbnail(info),
        "duration": int(duration) if isinstance(duration, (int, float)) else None,
        "duration_text": format_duration(duration),
        "uploader": uploader,
        "is_live": bool(info.get("is_live")),
        "ffmpeg_available": ffmpeg_ready,
        "formats": {
            "mp3": mp3_section,
            "audio": audio_section,
            "video": video_section,
        },
    }


def _base_options(cfg: Config) -> dict[str, Any]:
    options: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": True,
        "skip_download": True,
        "socket_timeout": 20,
        "retries": 3,
        "extractor_retries": 2,
        "nocheckcertificate": False,
        "cachedir": False,
    }
    if cfg.ffmpeg_path:
        options["ffmpeg_location"] = cfg.ffmpeg_path
    return options


def inspect_url(url: str, canonical_url: str, cfg: Config) -> dict[str, Any]:
    options = _base_options(cfg)
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as exc:
        raise MediaError(translate_error(str(exc))) from exc
    except Exception as exc:  # noqa: BLE001 - kullaniciya guvenli mesaj donulur
        raise MediaError(translate_error(str(exc))) from exc
    if not info:
        raise MediaError("Video bilgileri alinamadi. Baglantiyi kontrol edin.")
    if info.get("_type") == "playlist":
        entries = [entry for entry in (info.get("entries") or []) if entry]
        if not entries:
            raise MediaError("Bu baglanti tek bir videoya isaret etmiyor.")
        info = entries[0]
    return build_metadata(info, canonical_url, cfg)


def _estimate_selected_size(info: dict[str, Any], mode: str, quality: str) -> int | None:
    formats = info.get("formats") or []
    # The job cache contains the public, summarized format sections rather than
    # yt-dlp's raw format list. In that case a reliable byte estimate is not
    # available; let the download proceed without a preflight size estimate.
    if not isinstance(formats, list):
        return None
    if mode == "video":
        try:
            height = int(quality)
        except (TypeError, ValueError):
            return None
        candidates = []
        for fmt in formats:
            if not isinstance(fmt, dict) or fmt.get("vcodec") in (None, "none"):
                continue
            try:
                if fmt.get("height") and int(fmt["height"]) <= height:
                    candidates.append(fmt)
            except (TypeError, ValueError):
                continue
        if not candidates:
            return None
        best = max(candidates, key=lambda fmt: int(fmt.get("height") or 0))
        return best.get("filesize") or best.get("filesize_approx")
    if mode == "mp3":
        return None
    candidates = [
        fmt
        for fmt in formats
        if isinstance(fmt, dict) and fmt.get("vcodec") in (None, "none")
    ]
    if not candidates:
        return None
    if quality != "best":
        try:
            limit = int(quality)
        except (TypeError, ValueError):
            limit = None
        if limit:
            filtered = []
            for fmt in candidates:
                try:
                    if fmt.get("abr") and float(fmt["abr"]) <= limit:
                        filtered.append(fmt)
                except (TypeError, ValueError):
                    continue
            if filtered:
                candidates = filtered
    best = max(candidates, key=lambda fmt: float(fmt.get("abr") or 0))
    return best.get("filesize") or best.get("filesize_approx")


def estimate_selected_size(info: dict[str, Any], mode: str, quality: str) -> int | None:
    return _estimate_selected_size(info, mode, quality)


def _clean_for_log(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()
