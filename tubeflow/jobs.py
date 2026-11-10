"""Arka plan indirme isleri, ilerleme takibi ve dosya yonetimi."""

from __future__ import annotations

import shutil
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import yt_dlp

from .config import Config
from .history import HistoryStore
from .media import (
    MediaError,
    estimate_selected_size,
    inspect_url,
    translate_error,
)
from .security import TokenStore, ValidationError, safe_filename

MODE_LABELS = {
    "mp3": "MP3",
    "audio": "Yalnızca ses",
    "video": "MP4 video",
}
MODE_SKIPPED_STAGES = {
    "mp3": {"merging"},
    "audio": {"merging", "converting"},
    "video": {"converting"},
}
STAGE_ORDER = ("downloading", "merging", "converting", "ready")
STAGE_LABELS = {
    "downloading": "İndiriliyor",
    "merging": "Birleştiriliyor",
    "converting": "Dönüştürülüyor",
    "ready": "Hazır",
}
ACTIVE_STATUSES = {"queued", "downloading", "merging", "converting"}


def _iso(ts: float | None) -> str | None:
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


@dataclass
class Job:
    id: str
    url: str
    mode: str
    quality: str
    quality_label: str
    title: str
    thumbnail: str
    uploader: str
    duration: int | None
    duration_text: str
    status: str = "queued"
    stage: str = "downloading"
    percent: float | None = None
    downloaded_bytes: int | None = None
    total_bytes: int | None = None
    speed: float | None = None
    eta: int | None = None
    filename: str | None = None
    file_path: str | None = None
    size: int | None = None
    error: str | None = None
    token: str | None = None
    token_expires: float | None = None
    created_at: float = field(default_factory=time.time)
    finished_at: float | None = None

    @property
    def mode_label(self) -> str:
        return MODE_LABELS.get(self.mode, self.mode)

    def stages(self) -> list[dict[str, str]]:
        skipped = MODE_SKIPPED_STAGES.get(self.mode, set())
        if self.status == "queued":
            current_index = -1
        elif self.stage in STAGE_ORDER:
            current_index = STAGE_ORDER.index(self.stage)
        else:
            current_index = 0
        result = []
        for index, key in enumerate(STAGE_ORDER):
            if key in skipped:
                state = "skipped"
            elif self.status == "error" and key == self.stage:
                state = "error"
            elif self.status == "ready" or current_index > index:
                state = "done"
            elif current_index == index:
                state = "active"
            else:
                state = "pending"
            result.append({"key": key, "label": STAGE_LABELS[key], "state": state})
        return result


class JobManager:
    def __init__(
        self,
        cfg: Config,
        history: HistoryStore,
        tokens: TokenStore,
        inspector: Callable[[str, str, Config], dict[str, Any]] | None = None,
        downloader: Callable[..., Any] | None = None,
    ) -> None:
        self.cfg = cfg
        self.history = history
        self.tokens = tokens
        self._inspector = inspector or inspect_url
        self._downloader = downloader or yt_dlp.YoutubeDL
        self._jobs: dict[str, Job] = {}
        self._metadata_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._lock = threading.RLock()
        self._semaphore = threading.Semaphore(cfg.max_concurrent)

    # ------------------------------------------------------------------ inspect
    def inspect(self, url: str, canonical_url: str) -> dict[str, Any]:
        metadata = self._inspector(url, canonical_url, self.cfg)
        with self._lock:
            self._metadata_cache[canonical_url] = (time.time(), metadata)
        return metadata

    def _cached_metadata(self, canonical_url: str) -> dict[str, Any] | None:
        with self._lock:
            item = self._metadata_cache.get(canonical_url)
        if not item:
            return None
        cached_at, metadata = item
        if time.time() - cached_at > 1800:
            return None
        return metadata

    # ------------------------------------------------------------------ create
    def create(self, url: str, canonical_url: str, mode: str, quality: str) -> Job:
        if mode not in MODE_LABELS:
            raise ValidationError("Geçersiz indirme türü seçildi.")
        metadata = self._cached_metadata(canonical_url) or self.inspect(url, canonical_url)
        section = (metadata.get("formats") or {}).get(mode) or {}
        if not section.get("available"):
            raise ValidationError(section.get("reason") or "Bu indirme türü bu video için kullanılamıyor.")
        qualities = {item.get("value"): item.get("label") for item in section.get("qualities", [])}
        if quality not in qualities:
            raise ValidationError("Seçilen kalite bu video için mevcut değil.")

        job_id = uuid.uuid4().hex
        job_dir = self.cfg.download_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        job = Job(
            id=job_id,
            url=canonical_url,
            mode=mode,
            quality=quality,
            quality_label=qualities.get(quality) or quality,
            title=metadata.get("title") or "Bilinmeyen video",
            thumbnail=metadata.get("thumbnail") or "",
            uploader=metadata.get("uploader") or "",
            duration=metadata.get("duration"),
            duration_text=metadata.get("duration_text") or "",
        )
        with self._lock:
            self._jobs[job.id] = job
            self._prune_jobs_locked()
        thread = threading.Thread(
            target=self._run,
            args=(job, job_dir, metadata),
            name=f"tubeflow-job-{job.id[:8]}",
            daemon=True,
        )
        thread.start()
        return job

    # ------------------------------------------------------------------ run
    def _run(self, job: Job, job_dir: Path, metadata: dict[str, Any]) -> None:
        try:
            with self._semaphore:
                self._update(job.id, status="downloading", stage="downloading")
                self._ensure_disk_space(job_dir, estimate_selected_size(metadata, job.mode, job.quality))
                options = self._build_options(job, job_dir)
                with self._downloader(options) as ydl:
                    ydl.download([job.url])
                output = self._find_output(job_dir, job.mode)
                if output is None:
                    raise MediaError("İndirme tamamlandı ancak çıktı dosyası bulunamadı.")
                output = self._normalize_output(output)
                size = output.stat().st_size
                token = self.tokens.issue(job.id, output.name, job.title, size)
                finished = time.time()
                self._update(
                    job.id,
                    status="ready",
                    stage="ready",
                    percent=100.0,
                    speed=None,
                    eta=0,
                    filename=output.name,
                    file_path=str(output),
                    size=size,
                    token=token.token,
                    token_expires=token.expires_at,
                    finished_at=finished,
                )
                self._record_history(job, output.name, size, finished)
        except MediaError as exc:
            self._fail(job, str(exc))
        except Exception as exc:  # noqa: BLE001 - kullaniciya guvenli mesaj donulur
            self._fail(job, translate_error(str(exc)))

    def _fail(self, job: Job, message: str) -> None:
        job_dir = self.cfg.download_dir / job.id
        shutil.rmtree(job_dir, ignore_errors=True)
        self._update(job.id, status="error", error=message, speed=None, eta=None, percent=None)

    def _record_history(self, job: Job, filename: str, size: int, finished: float) -> None:
        record = {
            "id": job.id,
            "title": job.title,
            "thumbnail": job.thumbnail,
            "uploader": job.uploader,
            "filename": filename,
            "mode": job.mode,
            "mode_label": job.mode_label,
            "quality": job.quality,
            "quality_label": job.quality_label,
            "size": size,
            "duration": job.duration,
            "duration_text": job.duration_text,
            "finished_at": _iso(finished),
            "finished_ts": finished,
        }
        self.history.add(record)

    def _ensure_disk_space(self, job_dir: Path, estimated: int | None) -> None:
        try:
            free = shutil.disk_usage(job_dir).free
        except OSError:
            return
        needed = int(estimated or 0) + 200 * 1024 * 1024
        if free < needed:
            raise MediaError(
                "Yeterli disk alanı yok. İndirme için en az "
                f"{needed // (1024 * 1024)} MB boş alan gerekli."
            )

    # ------------------------------------------------------------------ yt-dlp
    def _build_options(self, job: Job, job_dir: Path) -> dict[str, Any]:
        outtmpl = str(job_dir / "%(title).150B [%(id)s].%(ext)s")
        options: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "noplaylist": True,
            "skip_download": False,
            "outtmpl": {"default": outtmpl},
            "paths": {"home": str(job_dir), "temp": str(job_dir)},
            "windowsfilenames": True,
            "overwrites": True,
            "continuedl": True,
            "retries": 5,
            "fragment_retries": 5,
            "socket_timeout": 30,
            "progress_hooks": [self._progress_hook(job)],
            "postprocessor_hooks": [self._postprocessor_hook(job)],
            "nocheckcertificate": False,
            "cachedir": False,
        }
        if self.cfg.ffmpeg_path:
            options["ffmpeg_location"] = self.cfg.ffmpeg_path

        if job.mode == "mp3":
            options["format"] = "bestaudio/best"
            options["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": job.quality,
                }
            ]
        elif job.mode == "audio":
            if job.quality == "best":
                options["format"] = "bestaudio/best"
            else:
                options["format"] = f"bestaudio[abr<={job.quality}]/bestaudio/best"
        else:
            height = int(job.quality)
            options["format"] = (
                f"bestvideo[ext=mp4][height<={height}]+bestaudio[ext=m4a]/"
                f"best[ext=mp4][height<={height}]/"
                f"bestvideo[height<={height}]+bestaudio/best[height<={height}]/best"
            )
            options["merge_output_format"] = "mp4"
            options["postprocessors"] = [
                {"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"}
            ]
        return options

    def _progress_hook(self, job: Job) -> Callable[[dict[str, Any]], None]:
        def hook(data: dict[str, Any]) -> None:
            status = data.get("status")
            if status == "downloading":
                total = data.get("total_bytes") or data.get("total_bytes_estimate")
                downloaded = data.get("downloaded_bytes")
                percent = None
                if total and downloaded is not None:
                    try:
                        percent = max(0.0, min(100.0, float(downloaded) / float(total) * 100.0))
                    except (TypeError, ValueError, ZeroDivisionError):
                        percent = None
                self._update(
                    job.id,
                    status="downloading",
                    stage="downloading",
                    percent=percent,
                    downloaded_bytes=downloaded,
                    total_bytes=total,
                    speed=data.get("speed"),
                    eta=data.get("eta"),
                )
            elif status == "finished":
                total = data.get("total_bytes") or data.get("total_bytes_estimate")
                self._update(
                    job.id,
                    downloaded_bytes=data.get("downloaded_bytes"),
                    total_bytes=total,
                    speed=None,
                    eta=None,
                )
        return hook

    def _postprocessor_hook(self, job: Job) -> Callable[[dict[str, Any]], None]:
        def hook(data: dict[str, Any]) -> None:
            name = str(data.get("postprocessor") or "").lower()
            status = data.get("status")
            if status != "started":
                return
            if "merger" in name or "remuxer" in name:
                self._update(job.id, status="merging", stage="merging", speed=None, eta=None)
            elif "extractaudio" in name:
                self._update(job.id, status="converting", stage="converting", speed=None, eta=None)
        return hook

    # ------------------------------------------------------------------ output
    def _find_output(self, job_dir: Path, mode: str) -> Path | None:
        try:
            files = [
                item
                for item in job_dir.iterdir()
                if item.is_file() and item.suffix.lower() not in {".part", ".ytdl", ".temp"}
            ]
        except OSError:
            return None
        if not files:
            return None
        if mode == "mp3":
            mp3_files = [item for item in files if item.suffix.lower() == ".mp3"]
            if mp3_files:
                return max(mp3_files, key=lambda item: item.stat().st_size)
        if mode == "video":
            video_files = [
                item
                for item in files
                if item.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov"}
            ]
            if video_files:
                return max(video_files, key=lambda item: item.stat().st_size)
        return max(files, key=lambda item: item.stat().st_size)

    def _normalize_output(self, output: Path) -> Path:
        safe_name = safe_filename(output.name)
        if safe_name == output.name:
            return output
        target = output.with_name(safe_name)
        if target.exists():
            target = output.with_name(f"{output.stem}-{uuid.uuid4().hex[:6]}{output.suffix}")
        try:
            output.rename(target)
            return target
        except OSError:
            return output

    # ------------------------------------------------------------------ state
    def _update(self, job_id: str, **changes: Any) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            for key, value in changes.items():
                setattr(job, key, value)

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def _prune_jobs_locked(self) -> None:
        if len(self._jobs) <= 100:
            return
        removable = [
            job.id
            for job in self._jobs.values()
            if job.status not in ACTIVE_STATUSES
        ]
        for job_id in removable[: len(self._jobs) - 100]:
            self._jobs.pop(job_id, None)

    def public(self, job: Job, lan_ip: str | None, lan_port: int | None) -> dict[str, Any]:
        data = {
            "id": job.id,
            "status": job.status,
            "stage": job.stage,
            "stage_label": STAGE_LABELS.get(job.stage, job.stage),
            "stages": job.stages(),
            "percent": job.percent,
            "downloaded_bytes": job.downloaded_bytes,
            "total_bytes": job.total_bytes,
            "speed": job.speed,
            "eta": job.eta,
            "title": job.title,
            "thumbnail": job.thumbnail,
            "uploader": job.uploader,
            "duration": job.duration,
            "duration_text": job.duration_text,
            "mode": job.mode,
            "mode_label": job.mode_label,
            "quality": job.quality,
            "quality_label": job.quality_label,
            "filename": job.filename,
            "size": job.size,
            "error": job.error,
            "created_at": _iso(job.created_at),
            "finished_at": _iso(job.finished_at),
            "download_url": None,
            "qr": {"available": False},
        }
        if job.status == "ready" and job.token:
            data["download_url"] = f"/api/jobs/{job.id}/file"
            if lan_ip and lan_port:
                data["qr"] = {
                    "available": True,
                    "url": f"http://{lan_ip}:{lan_port}/p/{job.token}",
                    "image": f"/api/jobs/{job.id}/qr.svg",
                    "expires_at": _iso(job.token_expires),
                }
            else:
                data["qr"] = {
                    "available": False,
                    "reason": "Yerel ağ adresi bulunamadı. Telefon aktarımı devre dışı.",
                }
        return data

    def file_path_for(self, job: Job) -> Path | None:
        return self._safe_existing_path(job.file_path)

    def history_file_path(self, job_id: str) -> Path | None:
        record = self.history.get(job_id)
        if not record:
            return None
        candidate = self.cfg.download_dir / job_id / str(record.get("filename") or "")
        return self._safe_existing_path(str(candidate))

    def _safe_existing_path(self, value: str | None) -> Path | None:
        if not value:
            return None
        base = self.cfg.download_dir.resolve()
        try:
            candidate = Path(value).resolve()
        except OSError:
            return None
        if base not in candidate.parents:
            return None
        if not candidate.is_file():
            return None
        return candidate
