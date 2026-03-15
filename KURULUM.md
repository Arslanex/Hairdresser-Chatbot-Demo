# Kurulum ve Başlatma Rehberi

## Gereksinimler

| Yazılım | Versiyon | İndirme |
|---------|----------|---------|
| Python | 3.11 – 3.13 | https://www.python.org/downloads/ |
| ngrok | Herhangi | https://ngrok.com/download |
| Node.js | 18+ (isteğe bağlı, Admin UI için) | https://nodejs.org/ |

> **Windows kurulumunda:** Python kurulurken **"Add Python to PATH"** seçeneğini işaretle.

---

## Hızlı Başlatma (Önerilen)

### Windows
```
start.bat çift tıkla
```

### Mac / Linux
```bash
./start.sh
```

Script her şeyi otomatik yapar: venv oluşturur, paketleri kurar, ngrok başlatır, sunucuyu açar.

---

## Manuel Başlatma (Adım Adım)

### 1. Projeyi indir / klonla
```bash
git clone <repo-url>
cd hairdreser-chatbot
```

### 2. .env dosyasını oluştur
```bash
# Windows
copy .env.example .env

# Mac / Linux
cp .env.example .env
```
`.env` dosyasını aç, API anahtarlarını gir.

### 3. Sanal ortam oluştur
```bash
python -m venv .venv
```

### 4. Sanal ortamı aktifleştir
```bash
# Windows
.venv\Scripts\activate

# Mac / Linux
source .venv/bin/activate
```

### 5. Paketleri kur
```bash
pip install -r requirements.txt
```

### 6. Admin UI derle (isteğe bağlı)
```bash
cd admin-ui
npm install
npm run build
cd ..
```

### 7. Sunucuyu başlat
```bash
python main.py
```
veya
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 8. ngrok başlat (yeni terminal penceresi)
```bash
ngrok http 8000
```
Ekranda görünen `https://xxxx.ngrok-free.app` adresi WhatsApp webhook URL'in olacak.

---

## WhatsApp Webhook Ayarı

1. [Meta Developer Console](https://developers.facebook.com/) → Uygulamana gir
2. **WhatsApp → Configuration → Webhook**
3. **Callback URL:** `https://xxxx.ngrok-free.app/webhook`
4. **Verify Token:** `.env` dosyasındaki `WHATSAPP_VERIFY_TOKEN` değeri
5. **Verify & Save** — ardından `messages` abone ol

> Her ngrok yeniden başladığında URL değişir, webhook'u güncellemen gerekir.
> Sabit URL için ngrok hesabı oluşturup statik domain kullanabilirsin.

---

## Durdurma

### Windows
```
stop.bat çift tıkla
```

### Mac / Linux
```bash
./stop.sh
```

### Manuel
```bash
# CTRL+C   (sunucu terminali)
# ngrok terminalini de kapat
```

---

## Adresler

| Sayfa | URL |
|-------|-----|
| API (sağlık kontrolü) | http://localhost:8000 |
| Admin paneli | http://localhost:8000/admin-ui |
| API dokümantasyonu | http://localhost:8000/docs |
| ngrok paneli | http://127.0.0.1:4040 |

---

## Sık Karşılaşılan Sorunlar

**`pydantic-core` kurulumda Rust hatası verdi**
→ Python 3.14 kullanıyorsun. Python 3.12 veya 3.13 kur, `.venv` klasörünü sil, tekrar başlat.

**Port 8000 kullanımda**
→ `stop.bat` / `stop.sh` çalıştır, yoksa görev yöneticisinden Python sürecini kapat.

**ngrok URL her seferinde değişiyor**
→ Beklenen davranış. Ücretsiz ngrok hesabı açıp statik domain alabilirsin: https://ngrok.com/
