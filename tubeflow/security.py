"""URL dogrulama, dosya adi guvenligi ve indirme tokenlari."""

from __future__ import annotations

import re
import secrets
import threading
import time
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

ALLOWED_HOSTS = {
    "youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
}

_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_INVALID_FILENAME_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WHITESPACE_RE = re.compile(r"\s+")


class ValidationError(ValueError):
    """Kullaniciya gosterilecek dogrulama hatasi."""


def parse_youtube_url(raw: str | None) -> tuple[str, str]:
    """YouTube baglantisini dogrular ve kanonik URL ile video kimligini dondurur."""
    if not raw or not raw.strip():
        raise ValidationError("Bir YouTube baglantisi yapistirin.")
    value = raw.strip()
    if len(value) > 2048:
        raise ValidationError("Baglanti cok uzun. Gecerli bir YouTube adresi yapistirin.")
    if "://" not in value:
        value = "https://" + value
    try:
        parsed = urlparse(value)
    except ValueError as exc:
        raise ValidationError("Baglanti okunamadi. Gecerli bir YouTube adresi yapistirin.") from exc
    if parsed.scheme not in ("http", "https"):
        raise ValidationError("Yalnizca http ve https baglantilari destekleniyor.")
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host not in ALLOWED_HOSTS:
        raise ValidationError("Yalnizca YouTube baglantilari destekleniyor.")

    video_id = None
    if host == "youtu.be":
        video_id = parsed.path.lstrip("/").split("/")[0]
    elif parsed.path == "/watch":
        video_id = parse_qs(parsed.query).get("v", [None])[0]
    elif parsed.path.startswith(("/shorts/", "/embed/", "/live/", "/v/")):
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2:
            video_id = parts[1]

    if not video_id or not _VIDEO_ID_RE.match(video_id):
        raise ValidationError("Baglantida gecerli bir video kimligi bulunamadi.")
    return f"https://www.youtube.com/watch?v={video_id}", video_id


def safe_filename(name: str | None, fallback: str = "tubeflow-dosya") -> str:
    """Isletim sisteminden bagimsiz, guvenli bir dosya adi uretir."""
    value = _INVALID_FILENAME_RE.sub("", (name or "").strip())
    value = _WHITESPACE_RE.sub(" ", value).strip(" .")
    if not value:
        value = fallback
    stem, dot, ext = value.rpartition(".")
    if dot and 1 <= len(ext) <= 6 and ext.isalnum():
        base = stem[:120].rstrip(" .") or fallback
        return f"{base}.{ext.lower()}"
    return value[:120].rstrip(" .") or fallback


def is_loopback(remote_addr: str | None) -> bool:
    if not remote_addr:
        return False
    return remote_addr in {"127.0.0.1", "::1", "localhost"} or remote_addr.startswith("127.")


@dataclass
class TokenRecord:
    token: str
    job_id: str
    filename: str
    title: str
    size: int
    expires_at: float

    @property
    def expires_at_iso(self) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.expires_at))


class TokenStore:
    """Tahmin edilemeyen, sureli ve is kaydina bagli indirme tokenlari."""

    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = ttl_seconds
        self._items: dict[str, TokenRecord] = {}
        self._lock = threading.Lock()

    def issue(self, job_id: str, filename: str, title: str, size: int) -> TokenRecord:
        record = TokenRecord(
            token=secrets.token_urlsafe(32),
            job_id=job_id,
            filename=filename,
            title=title,
            size=size,
            expires_at=time.time() + self._ttl,
        )
        with self._lock:
            self._purge_locked()
            self._items[record.token] = record
        return record

    def resolve(self, token: str | None) -> TokenRecord | None:
        if not token:
            return None
        with self._lock:
            self._purge_locked()
            return self._items.get(token)

    def revoke(self, token: str) -> None:
        with self._lock:
            self._items.pop(token, None)

    def _purge_locked(self) -> None:
        now = time.time()
        expired = [key for key, record in self._items.items() if record.expires_at <= now]
        for key in expired:
            self._items.pop(key, None)

    def purge(self) -> None:
        with self._lock:
            self._purge_locked()
