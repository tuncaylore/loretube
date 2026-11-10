"""Flask uygulamalari: yerel arayuz ve sinirli yerel ag paylasimi."""

from __future__ import annotations

import io

import qrcode
import qrcode.image.svg
from flask import (
    Flask,
    Response,
    jsonify,
    render_template,
    request,
    send_file,
)

from .config import Config
from .history import HistoryStore
from .jobs import JobManager
from .media import MediaError
from .security import TokenStore, ValidationError, is_loopback, parse_youtube_url

MAIN_CSP = (
    "default-src 'self'; "
    "img-src 'self' data: https:; "
    "style-src 'self'; "
    "script-src 'self'; "
    "connect-src 'self'; "
    "font-src 'self'; "
    "base-uri 'none'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)
SHARE_CSP = (
    "default-src 'none'; "
    "style-src 'unsafe-inline'; "
    "img-src 'self' data:; "
    "base-uri 'none'; "
    "form-action 'none'; "
    "frame-ancestors 'none'"
)


class AppState:
    def __init__(
        self,
        cfg: Config,
        history: HistoryStore,
        tokens: TokenStore,
        jobs: JobManager,
        lan_ip: str | None,
    ) -> None:
        self.cfg = cfg
        self.history = history
        self.tokens = tokens
        self.jobs = jobs
        self.lan_ip = lan_ip
        self.lan_port: int | None = None


def _json_error(message: str, status: int = 400) -> tuple[Response, int]:
    response = jsonify({"ok": False, "error": message})
    response.status_code = status
    return response


def _qr_svg(payload: str) -> bytes:
    image = qrcode.make(
        payload,
        image_factory=qrcode.image.svg.SvgPathImage,
        box_size=10,
        border=2,
    )
    buffer = io.BytesIO()
    image.save(buffer)
    return buffer.getvalue()


def _add_headers(response: Response, csp: str) -> Response:
    response.headers["Content-Security-Policy"] = csp
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


def create_app(state: AppState) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(state.cfg.template_dir),
        static_folder=str(state.cfg.static_dir),
        static_url_path="/static",
    )
    app.json.ensure_ascii = False
    app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024

    @app.before_request
    def _loopback_only():
        if not is_loopback(request.remote_addr):
            return _json_error("Bu arayüze yalnızca bu bilgisayardan erişilebilir.", 403)
        return None

    @app.after_request
    def _headers(response: Response) -> Response:
        _add_headers(response, MAIN_CSP)
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/")
    def index() -> str:
        return render_template(
            "index.html",
            lan_available=bool(state.lan_ip and state.lan_port),
            lan_ip=state.lan_ip or "",
            ffmpeg_available=bool(state.cfg.ffmpeg_path),
            token_ttl_hours=max(1, state.cfg.token_ttl // 3600),
        )

    @app.post("/api/inspect")
    def api_inspect() -> tuple[Response, int] | Response:
        data = request.get_json(silent=True) or {}
        try:
            url, _video_id = parse_youtube_url(data.get("url"))
        except ValidationError as exc:
            return _json_error(str(exc), 400)
        try:
            metadata = state.jobs.inspect(url, url)
        except MediaError as exc:
            return _json_error(str(exc), 422)
        return jsonify({"ok": True, "video": metadata})

    @app.post("/api/download")
    def api_download() -> tuple[Response, int] | Response:
        data = request.get_json(silent=True) or {}
        try:
            url, _video_id = parse_youtube_url(data.get("url"))
            mode = str(data.get("mode") or "").strip()
            quality = str(data.get("quality") or "").strip()
            job = state.jobs.create(url, url, mode, quality)
        except ValidationError as exc:
            return _json_error(str(exc), 400)
        except MediaError as exc:
            return _json_error(str(exc), 422)
        return jsonify({"ok": True, "job": state.jobs.public(job, state.lan_ip, state.lan_port)})

    @app.get("/api/jobs/<job_id>")
    def api_job(job_id: str) -> tuple[Response, int] | Response:
        job = state.jobs.get(job_id)
        if not job:
            return _json_error("İş bulunamadı.", 404)
        return jsonify({"ok": True, "job": state.jobs.public(job, state.lan_ip, state.lan_port)})

    @app.get("/api/jobs/<job_id>/file")
    def api_job_file(job_id: str) -> tuple[Response, int] | Response:
        job = state.jobs.get(job_id)
        if not job or job.status != "ready":
            return _json_error("Dosya henüz hazır değil.", 404)
        path = state.jobs.file_path_for(job)
        if not path:
            return _json_error("Dosya diskte bulunamadı.", 404)
        return send_file(path, as_attachment=True, download_name=job.filename or path.name)

    @app.get("/api/jobs/<job_id>/qr.svg")
    def api_job_qr(job_id: str) -> tuple[Response, int] | Response:
        job = state.jobs.get(job_id)
        if not job or job.status != "ready" or not job.token:
            return _json_error("QR kod için hazır bir dosya yok.", 404)
        if not state.lan_ip or not state.lan_port:
            return _json_error("Yerel ağ adresi bulunamadı.", 409)
        payload = f"http://{state.lan_ip}:{state.lan_port}/p/{job.token}"
        try:
            svg = _qr_svg(payload)
        except Exception:  # noqa: BLE001 - QR uretimi basarisizsa guvenli yanit
            return _json_error("QR kod oluşturulamadı.", 500)
        response = Response(svg, mimetype="image/svg+xml")
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/history")
    def api_history() -> Response:
        items = []
        for record in state.history.list():
            item = dict(record)
            job_id = item.get("id")
            item["available"] = bool(state.jobs.history_file_path(job_id)) if job_id else False
            item["download_url"] = f"/api/history/{job_id}/file" if item["available"] else None
            items.append(item)
        return jsonify({"ok": True, "items": items})

    @app.get("/api/history/<job_id>/file")
    def api_history_file(job_id: str) -> tuple[Response, int] | Response:
        record = state.history.get(job_id)
        if not record:
            return _json_error("Geçmiş kaydı bulunamadı.", 404)
        path = state.jobs.history_file_path(job_id)
        if not path:
            return _json_error("Dosya diskte bulunamadı. Saklama süresi dolmuş olabilir.", 404)
        return send_file(
            path,
            as_attachment=True,
            download_name=str(record.get("filename") or path.name),
        )

    @app.get("/api/health")
    def api_health() -> Response:
        return jsonify(
            {
                "ok": True,
                "lan_available": bool(state.lan_ip and state.lan_port),
                "ffmpeg_available": bool(state.cfg.ffmpeg_path),
            }
        )

    @app.errorhandler(404)
    def _not_found(_error: object) -> tuple[Response, int]:
        if request.path.startswith("/api/"):
            return _json_error("İstenen kaynak bulunamadı.", 404)
        return _json_error("Sayfa bulunamadı.", 404)

    @app.errorhandler(413)
    def _too_large(_error: object) -> tuple[Response, int]:
        return _json_error("Gönderilen istek çok büyük.", 413)

    return app


def create_share_app(state: AppState) -> Flask:
    app = Flask(
        __name__ + "-share",
        template_folder=str(state.cfg.template_dir),
        static_folder=None,
    )
    app.json.ensure_ascii = False

    @app.after_request
    def _headers(response: Response) -> Response:
        _add_headers(response, SHARE_CSP)
        response.headers["Cache-Control"] = "no-store"
        return response

    def _resolve(token: str):
        record = state.tokens.resolve(token)
        if not record:
            return None, None
        job = state.jobs.get(record.job_id)
        if job and job.status == "ready":
            path = state.jobs.file_path_for(job)
        else:
            path = state.jobs.history_file_path(record.job_id)
        if not path:
            return record, None
        return record, path

    @app.get("/p/<token>")
    def phone_page(token: str):
        record, path = _resolve(token)
        if not record:
            return render_template("phone_invalid.html", reason="Bağlantı geçersiz veya süresi dolmuş."), 404
        if not path:
            return render_template("phone_invalid.html", reason="Dosya artık mevcut değil."), 410
        return render_template(
            "phone.html",
            title=record.title,
            filename=record.filename,
            size=record.size,
            token=token,
        )

    @app.get("/p/<token>/file")
    def phone_file(token: str):
        record, path = _resolve(token)
        if not record or not path:
            return render_template("phone_invalid.html", reason="Bağlantı geçersiz veya süresi dolmuş."), 404
        return send_file(path, as_attachment=True, download_name=record.filename)

    @app.get("/health")
    def health() -> Response:
        return jsonify({"ok": True})

    return app
