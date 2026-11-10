# TubeFlow

TubeFlow; herkese açık YouTube videolarını incelemek ve indirme izniniz olan içerikleri kaydetmek için Windows'ta yerel çalışan bir Flask uygulamasıdır. Ses ve video indirme, FFmpeg ile MP3 dönüştürme, indirme ilerlemesini izleme, yerel geçmiş ve aynı Wi-Fi ağındaki telefona geçici QR bağlantısıyla dosya aktarma özelliklerini sunar.

![TubeFlow uygulama ekran görüntüsü](screenshoot.png)

## Windows'ta başlatma

1. Python 3.10 veya üzeri sürümü kurun; Python başlatıcısının (`py`) kullanılabilir olduğundan emin olun.
2. `run.bat` dosyasına çift tıklayın. Gerekirse `.venv` sanal ortamını oluşturur, `requirements.txt` içindeki paketleri kurar ve uygulamayı başlatır.
3. Tarayıcı kendiliğinden açılmazsa `http://127.0.0.1:5000` adresine gidin. Uygulamayı durdurmak için terminali kapatın veya Ctrl+C tuşlarına basın.

İlk başlatmada `run.bat`, FFmpeg'i kontrol eder. FFmpeg kurulu değilse ffmpeg.org'un işaret ettiği Windows derleme sağlayıcısı Gyan.dev'den gerekli ZIP dosyasını indirir, yayımlanan SHA-256 özetiyle doğrular ve çalıştırılabilir dosyaları `tools/ffmpeg/bin/` klasörüne kurar. Sistem PATH'i değiştirilmez ve yönetici izni gerekmez. İndirme veya doğrulama başarısız olsa da uygulama açılır; FFmpeg gerektiren özellikler kullanılamayabilir. Var olan FFmpeg konumunu `TUBEFLOW_FFMPEG` ortam değişkeniyle belirtebilirsiniz.

## Elle çalıştırma

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe run.py
```

Ana arayüz yalnızca `127.0.0.1` adresinde çalışır. Telefona aktarım ayrı bir yerel ağ sunucusu ve tahmin edilemeyen, süresi dolan bir token kullanır; iki cihazın aynı Wi-Fi ağında olması gerekir. İnternete açık sunucu veya yönlendiricide port yönlendirme yapılandırılmaz. Yerel ağ aktarımı etkinleştirilirken güvenlik duvarı izni istenebilir.

## Yapılandırma

Ortam değişkenleri: `TUBEFLOW_PORT` (varsayılan `5000`), `TUBEFLOW_LAN_PORT` (varsayılan `5001`), `TUBEFLOW_LAN_IP` (isteğe bağlı özel IPv4 adresi), `TUBEFLOW_FFMPEG`, `TUBEFLOW_DOWNLOAD_DIR`, `TUBEFLOW_DATA_DIR`, `TUBEFLOW_TOKEN_TTL` (saniye), `TUBEFLOW_RETENTION_DAYS`, `TUBEFLOW_MAX_HISTORY`, `TUBEFLOW_MAX_CONCURRENT` ve `TUBEFLOW_NO_BROWSER=1`.

İndirilen dosyalar `downloads/` klasörüne, başarılı işlemlerin bilgileri `data/history.json` dosyasına kaydedilir. Varsayılan olarak yedi günden eski indirmeler uygulama başlarken temizlenir.

TubeFlow'u yalnızca indirme izniniz olan herkese açık içerikler için kullanın. Telif haklarına ve YouTube Kullanım Şartları'na uyun. Özel veya üyelik kısıtlamalı içeriklere erişme ya da erişim kontrollerini aşma iş akışları desteklenmez.
