# TubeFlow

TubeFlow is a local Flask app for inspecting publicly accessible YouTube videos and downloading content the user is authorized to save. It supports audio, MP3 conversion (FFmpeg required), video downloads, progress reporting, local history, and temporary QR links for transfer to a phone on the same local network.

## Start on Windows

1. Install Python 3.10 or newer and make sure the Python launcher (`py`) is available.
2. Double-click `run.bat`. It creates `.venv` if needed, installs the dependencies from `requirements.txt`, and starts the app.
3. Open `http://127.0.0.1:5000` if the browser does not open automatically. Close the terminal or press Ctrl+C to stop TubeFlow.

On first start, `run.bat` checks for FFmpeg and, if missing, downloads the Windows essentials ZIP from Gyan.dev (a Windows build provider linked by ffmpeg.org), verifies its published SHA-256 checksum, and installs the executables under `tools/ffmpeg/bin/`. No system-wide PATH changes or administrator permissions are needed; LoreFlow discovers this project-local path automatically. If the download or checksum verification fails, the app still starts with FFmpeg-dependent options unavailable. You can also set `TUBEFLOW_FFMPEG` to an existing FFmpeg executable or its containing directory.

## Run manually

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe run.py
```

The main interface binds to `127.0.0.1`. Phone transfer uses a separate local-network server and an unguessable, expiring token; both devices must be on the same Wi-Fi. No internet-facing server or router port forwarding is configured. A firewall prompt may appear when enabling local-network transfer.

## Configuration

Environment variables: `TUBEFLOW_PORT` (default `5000`), `TUBEFLOW_LAN_PORT` (default `5001`), `TUBEFLOW_LAN_IP` (optional private IPv4 override), `TUBEFLOW_FFMPEG`, `TUBEFLOW_DOWNLOAD_DIR`, `TUBEFLOW_DATA_DIR`, `TUBEFLOW_TOKEN_TTL` (seconds), `TUBEFLOW_RETENTION_DAYS`, `TUBEFLOW_MAX_HISTORY`, `TUBEFLOW_MAX_CONCURRENT`, and `TUBEFLOW_NO_BROWSER=1`.

Downloads are stored in `downloads/`; successful-job metadata is stored in `data/history.json`. By default, downloads older than seven days are removed on startup.

Only use TubeFlow for public content you are authorized to download. Respect copyright and YouTube's terms. Private, membership-restricted, and access-control-bypassing workflows are not supported.

## Supporters

- [Meyremsenge](https://github.com/Meyremsenge)
- [zehraabut](https://github.com/zehraabut)
