"""TubeFlow baslatici: yerel arayuz ve sinirli LAN paylasim sunucusu."""

from __future__ import annotations

import socket
import sys
import threading
import time
import webbrowser

from werkzeug.serving import make_server

from .config import Config
from .history import HistoryStore
from .jobs import JobManager
from .network import get_lan_ip
from .security import TokenStore
from .web import AppState, create_app, create_share_app


def _find_free_port(host: str, start: int, exclude: set[int] | None = None) -> int | None:
    exclude = exclude or set()
    for port in range(start, start + 50):
        if port in exclude:
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
            except OSError:
                continue
            return port
    return None


def _banner(message: str) -> None:
    print(message, flush=True)


def build_state(cfg: Config) -> AppState:
    history = HistoryStore(cfg.history_file, cfg.max_history)
    tokens = TokenStore(cfg.token_ttl)
    jobs = JobManager(cfg, history, tokens)
    lan_ip = get_lan_ip(cfg.lan_ip_override)
    return AppState(cfg=cfg, history=history, tokens=tokens, jobs=jobs, lan_ip=lan_ip)


def main() -> int:
    cfg = Config()
    _banner("")
    _banner("TubeFlow başlatılıyor…")
    if cfg.ffmpeg_path:
        _banner(f"FFmpeg bulundu: {cfg.ffmpeg_path}")
    else:
        _banner("[UYARI] FFmpeg bulunamadı. MP3 ve video birleştirme devre dışı kalacak.")

    state = build_state(cfg)
    state.history.remove_missing(cfg.download_dir)
    removed = state.history.prune_older_than(cfg.retention_days, cfg.download_dir)
    if removed:
        _banner(f"Saklama süresi dolan {len(removed)} dosya temizlendi.")

    main_port = _find_free_port(cfg.host, cfg.port)
    if main_port is None:
        _banner(
            f"[HATA] {cfg.port} portundan itibaren boş port bulunamadı. "
            "Çalışan diğer uygulamaları kapatıp yeniden deneyin."
        )
        return 1
    if main_port != cfg.port:
        _banner(f"[BİLGİ] {cfg.port} portu dolu; {main_port} portu kullanılacak.")

    if state.lan_ip:
        lan_port = _find_free_port("0.0.0.0", cfg.lan_port, exclude={main_port})
        if lan_port is None:
            _banner("[UYARI] Telefon aktarımı için boş port bulunamadı; QR devre dışı.")
            state.lan_ip = None
        else:
            state.lan_port = lan_port
    else:
        _banner("[BİLGİ] Yerel ağ adresi bulunamadı; QR ile telefon aktarımı devre dışı.")

    app = create_app(state)

    if state.lan_ip and state.lan_port:
        share_app = create_share_app(state)
        share_server = make_server("0.0.0.0", state.lan_port, share_app, threaded=True)
        threading.Thread(
            target=share_server.serve_forever,
            name="tubeflow-lan-server",
            daemon=True,
        ).start()
        _banner(
            f"Telefon aktarımı hazır: http://{state.lan_ip}:{state.lan_port} "
            "(yalnızca aynı Wi-Fi ağındaki telefonlar, süreli token ile)"
        )

    url = f"http://{cfg.host}:{main_port}/"
    _banner(f"TubeFlow hazır: {url}")
    _banner("Kapatmak için bu pencerede Ctrl+C tuşlarına basın.")
    _banner("")

    if not cfg.no_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    try:
        app.run(
            host=cfg.host,
            port=main_port,
            debug=False,
            use_reloader=False,
            threaded=True,
        )
    except KeyboardInterrupt:
        _banner("TubeFlow kapatılıyor…")
    return 0


if __name__ == "__main__":
    sys.exit(main())
