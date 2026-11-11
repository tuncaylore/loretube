# Düzeltme raporu: Masaüstü TubeFlow başlatma simgesi

**Tarih:** 2026-11-11

## Sorun ve gözlenen belirtiler

Kullanıcı `run.bat` çalıştırıldığında masaüstünde YouTube tarzı simgeli bir uygulama başlatma kısayolu oluşmasını istedi. Önceki `run.bat` akışı Python ortamını/paketlerini hazırlayıp `run.py` dosyasını çalıştırıyordu; masaüstü kısayolu oluşturmuyordu.

## Olası kök neden

İlk düzeltmeden önce `run.bat` içinde kısayol üretimi veya ikon oluşturma adımı bulunmuyordu. Projede masaüstü `.lnk` kısayolu ya da Windows kısayolunun kullanabileceği bir YouTube tarzı `.ico` dosyası da yoktu. İlk düzeltme kısayolu oluşturdu; ancak `run.bat`, `-ProjectDir` argümanını `"%~dp0"` olarak, yani kapanış tırnağından hemen önce `\` ile biten yolla iletiyordu. Windows'un komut satırı argüman ayrıştırması bu sondaki ters eğik çizgiyi yanlış ele alarak PowerShell'e geçersiz karakter içeren bir yol aktarıyor. Eski komut biçimi `cmd.exe` üzerinden yeniden çalıştırıldığında kullanıcının bildirdiği "Yolda geçersiz karakterler var" hatası aynen üretildi.

## Yapılan düzeltmeler

| Dosya | Değişiklik |
| --- | --- |
| `run.bat` | Uygulama başlatma adımlarından önce `create_desktop_shortcut.ps1` betiğini çağırır. Proje yolunu `"%~dp0."` ile göndererek tırnak/son ters eğik çizgi sorununu önler. Kısayol oluşturma başarısız olsa bile başlatma akışını sürdürür. |
| `create_desktop_shortcut.ps1` | Windows PowerShell ve WScript.Shell ile 256×256 YouTube tarzı kırmızı oynat simgeli ICO üretir ve masaüstünde `TubeFlow - YouTube Baslat.lnk` kısayolunu oluşturur/günceller. Kısayol `run.bat` dosyasını doğru çalışma klasöründe açar. |
| `README.md` | Windows başlatma yönergelerine masaüstü kısayolu davranışını ekler. |
| `.gitignore` | `fix.md` dosyasının genel Markdown dışlama kuralına takılmaması için istisna ekler. |

Oluşturulan yerel ikon `tools/tubeflow-youtube.ico` konumundadır; `tools/` zaten çalışma zamanı çıktıları için Git dışında tutulur. Bu çalışma sırasında masaüstü kısayolu da oluşturuldu: `C:\Users\TuncayErol\Desktop\TubeFlow - YouTube Baslat.lnk`.

## Doğrulama

| Kontrol | Beklenen sonuç | Sonuç |
| --- | --- | --- |
| PowerShell ayrıştırıcısıyla `create_desktop_shortcut.ps1` sözdizimini denetleme | Ayrıştırma hatası olmaması | **Başarılı** — `PowerShell syntax OK`. |
| `& ".\create_desktop_shortcut.ps1" -ProjectDir "C:\Users\TuncayErol\Desktop\LORE_tubeflow"` | ICO ve masaüstü kısayolunun oluşturulması | **Başarılı** — betik masaüstü kısayolunun hazır olduğunu bildirdi. |
| Oluşan `.ico` dosyasını `System.Drawing` ile açma; `.lnk` hedefi ve simge yolunu kontrol etme | ICO dosyası çözümlenmeli; kısayol hedefi proje içindeki `run.bat`, çalışma klasörü proje kökü ve ikon yolu oluşturulan ICO olmalı | **Başarılı** — 2.590 baytlık ICO Windows çizim API'si ile 256×256 olarak açıldı; kısayol hedefi `run.bat` ve simge yolu doğru. |
| `git diff --check` | Boşluk/patch hatası olmaması | **Başarılı** — `git diff --check: OK`. |
| `cmd.exe` üzerinden eski ve düzeltilmiş PowerShell çağrı biçimlerini çalıştırma | Eski biçimde hata yeniden üretilebilmeli; düzeltilmiş biçimde kısayol oluşturulmalı | **Başarılı** — eski `"%~dp0"` biçimi "Yolda geçersiz karakterler var" hatasını üretti. Düzeltilmiş `"%~dp0."` biçimiyle betik kısayolu başarıyla oluşturdu. |

Depoda `requirements.txt` dışında test/lint/build yapılandırması veya `tests/`, `tubeflow/test*.py`, `tubeflow/test_*.py` eşleşmesi bulunmadı. `run.bat` uçtan uca çalıştırılmadı; bu komut uygulamayı ve olası paket kurulumunu başlatır. Dolayısıyla kısayol üretimi bağımsız olarak çalıştırılıp doğrulandı, fakat masaüstü kısayoluna çift tıklayarak uygulamayı açma testi yapılmadı.

## Bilinmeyenler ve kalan riskler

- Kısayol, bu proje klasöründeki `run.bat` dosyasına ve `tools/tubeflow-youtube.ico` ikonuna işaret eder. Proje klasörü taşınırsa kısayolun hedefi geçersiz kalabilir; projedeki `run.bat` tekrar çalıştırıldığında kısayol güncellenir.
- Kurum ilkeleri PowerShell/COM kullanımını engelliyorsa masaüstü kısayolu oluşturulamayabilir. Bu durumda `run.bat` uyarı verir ve uygulamayı başlatmayı yine dener.
- Masaüstü kısayoluna çift tıklayıp uygulamanın tam açılışını doğrulama bu çalışmada yapılmadı.
