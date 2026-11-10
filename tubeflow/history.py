"""Tamamlanan islerin hafif JSON gecmisi."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path


class HistoryStore:
    def __init__(self, path: Path, max_items: int = 50) -> None:
        self._path = Path(path)
        self._max_items = max(1, max_items)
        self._items: list[dict] = []
        self._lock = threading.Lock()
        self._load()

    def _load(self) -> None:
        if not self._path.is_file():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if isinstance(data, list):
            self._items = [item for item in data if isinstance(item, dict)][: self._max_items]

    def _save_locked(self) -> None:
        payload = json.dumps(self._items, ensure_ascii=False, indent=2)
        temp = self._path.with_suffix(".tmp")
        try:
            temp.write_text(payload, encoding="utf-8")
            temp.replace(self._path)
        except OSError:
            try:
                self._path.write_text(payload, encoding="utf-8")
            except OSError:
                pass

    def add(self, record: dict) -> None:
        with self._lock:
            self._items = [item for item in self._items if item.get("id") != record.get("id")]
            self._items.insert(0, record)
            self._items = self._items[: self._max_items]
            self._save_locked()

    def list(self) -> list[dict]:
        with self._lock:
            return list(self._items)

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            for item in self._items:
                if item.get("id") == job_id:
                    return dict(item)
        return None

    def remove_missing(self, download_dir: Path) -> None:
        base = Path(download_dir).resolve()
        with self._lock:
            kept: list[dict] = []
            changed = False
            for item in self._items:
                job_id = item.get("id")
                filename = item.get("filename")
                if not job_id or not filename:
                    changed = True
                    continue
                candidate = (base / job_id / filename).resolve()
                if base in candidate.parents and candidate.is_file():
                    kept.append(item)
                else:
                    changed = True
            if changed:
                self._items = kept
                self._save_locked()

    def prune_older_than(self, days: int, download_dir: Path) -> list[str]:
        """Saklama suresini asan kayitlari ve dosyalarini siler, silinen isleri dondurur."""
        import shutil

        cutoff = time.time() - days * 86400
        removed: list[str] = []
        with self._lock:
            kept: list[dict] = []
            for item in self._items:
                finished = item.get("finished_ts") or 0
                if finished and finished < cutoff:
                    job_id = item.get("id")
                    if job_id:
                        folder = Path(download_dir) / job_id
                        if folder.is_dir():
                            shutil.rmtree(folder, ignore_errors=True)
                        removed.append(job_id)
                else:
                    kept.append(item)
            if removed:
                self._items = kept
                self._save_locked()
        return removed
