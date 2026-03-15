# Kuaför Chatbot

WhatsApp üzerinden çalışan Türkçe kuaför randevu chatbotu. FastAPI, Claude claude-opus-4-6 ve WhatsApp Cloud API kullanır.

---

## Gereksinimler

- Python 3.11+
- [Anthropic API anahtarı](https://console.anthropic.com/)
- [WhatsApp Business hesabı ve Cloud API erişimi](https://developers.facebook.com/docs/whatsapp/cloud-api/get-started)

---

## Kurulum

```bash
# Depoyu klonla
git clone <repo-url>
cd hairdresser-chatbot

# Sanal ortam oluştur ve aktif et
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Bağımlılıkları yükle
pip install -r requirements.txt

# Ortam değişkenlerini ayarla
cp .env.example .env
# .env dosyasını düzenleyip gerçek değerleri gir (aşağıya bak)
```

---

## Ortam Değişkenleri (`.env`)

| Değişken | Zorunlu | Açıklama |
|---|---|---|
| `ANTHROPIC_API_KEY` | ✅* | Anthropic Claude API anahtarı (* Groq kullanılmıyorsa) |
| `USE_GROQ_LLM` | — | `1` = test/uygulama LLM olarak Groq kullanır (hızlı/ekonomik) |
| `GROQ_API_KEY` | ✅** | Groq Cloud API anahtarı (** `USE_GROQ_LLM=1` ise; [console.groq.com](https://console.groq.com/)) |
| `GROQ_MODEL` | — | Groq model (varsayılan: `llama-3.3-70b-versatile`) |
| `WHATSAPP_TOKEN` | ✅ | WhatsApp Cloud API bearer token |
| `WHATSAPP_PHONE_NUMBER_ID` | ✅ | WhatsApp Business telefon numarası ID'si |
| `WHATSAPP_VERIFY_TOKEN` | ✅ | Webhook doğrulama için rastgele bir string |
| `WHATSAPP_APP_SECRET` | ⚠️ | Meta uygulama gizli anahtarı (imza doğrulama için — prod'da zorunlu) |
| `DATABASE_URL` | — | SQLAlchemy async URL (varsayılan: SQLite) |
| `BUSINESS_NAME` | — | Salon adı |
| `BUSINESS_PHONE` | — | Salon telefonu |
| `BUSINESS_ADDRESS` | — | Salon adresi |
| `WORKING_HOURS_START` | — | Açılış saati, 24 saat formatı (varsayılan: 9) |
| `WORKING_HOURS_END` | — | Kapanış saati (varsayılan: 19) |
| `WORKING_DAYS` | — | Çalışma günleri JSON dizisi, 0=Pazartesi (varsayılan: `[0,1,2,3,4,5]`) |
| `CONVERSATION_TIMEOUT_HOURS` | — | Oturum zaman aşımı (varsayılan: 4) |

> **`WORKING_DAYS` formatı:** `.env` dosyasında JSON dizisi olarak yazılmalıdır: `WORKING_DAYS=[0,1,2,3,4,5]`

---

## Çalıştırma

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Uygulama başladığında:
- Veritabanı tabloları otomatik oluşturulur (`SQLite` için `hairdresser.db`)
- `GET /` sağlık kontrolü: `{"status": "ok", "db": "ok"}`

---

## WhatsApp Webhook Ayarı

WhatsApp, webhook URL'nize POST istekleri gönderir. Geliştirme ortamında [ngrok](https://ngrok.com/) gibi bir tünel aracıyla public URL oluşturabilirsiniz:

```bash
ngrok http 8000
```

### 1. Webhook URL'sini kaydet

Meta Developer Console → App → WhatsApp → Configuration:

- **Callback URL:** `https://<ngrok-id>.ngrok.io/webhook`
- **Verify Token:** `.env` dosyasındaki `WHATSAPP_VERIFY_TOKEN` değeri

### 2. Webhook doğrulaması

WhatsApp, kayıt sırasında `GET /webhook?hub.mode=subscribe&hub.challenge=...&hub.verify_token=...` isteği gönderir. Uygulama token'ı eşleştirip `hub.challenge`'ı döndürür.

### 3. İmza doğrulaması (prod)

Meta → App Settings → App Secret değerini `.env` dosyasına `WHATSAPP_APP_SECRET` olarak ekleyin. Eksikse imza kontrolü atlanır (yalnızca lokal geliştirme için).

---

## Proje Yapısı

```
├── main.py                          # FastAPI uygulaması, lifespan, health check
├── config.py                        # Pydantic-settings ile ortam değişkenleri
├── api/
│   └── webhook.py                   # GET (doğrulama) + POST (mesaj alma) endpoint
├── integrations/
│   └── whatsapp/
│       ├── client.py                # WhatsApp Cloud API HTTP client
│       └── message_processor.py     # Webhook payload ayrıştırma + idempotans
├── services/
│   ├── ai_service.py                # Claude orkestrasyonu, niyet yönlendirme
│   ├── booking_service.py           # Randevu CRUD
│   ├── knowledge_service.py         # Salon bilgileri, çalışma saatleri
│   ├── session_manager.py           # Oturum durumu yönetimi
│   └── user_service.py              # Kullanıcı CRUD
├── ai/
│   ├── intent_classifier.py         # Claude Haiku ile niyet sınıflandırma
│   ├── context_guard.py             # Kapsam dışı mesaj filtresi
│   └── date_time_parser.py          # Türkçe tarih/saat ayrıştırma
├── conversation_flows/
│   ├── flow_engine.py               # Adım geçişleri, validasyon yönlendirme
│   └── booking_flow.py              # Randevu adımları, mesaj üreticiler
├── database/
│   ├── connection.py                # SQLAlchemy engine, session, init_db
│   └── models.py                    # User, Booking, Session, ProcessedMessage
└── terminal_chat.py                 # Lokal test için terminal arayüzü
```

---

## Testler

Varsayılan olarak testler gerçek LLM çağrısı yapmaz (Anthropic dummy key ile config yüklenir). **Testlerde Groq kullanmak** (daha hızlı ve ekonomik) için `.env` dosyasına ekleyin:

```bash
USE_GROQ_LLM=1
GROQ_API_KEY=gsk_...   # https://console.groq.com/ adresinden alın
```

Ardından: `pytest tests/`

---

## Lokal Test

Webhook olmadan terminal üzerinden test etmek için:

```bash
python terminal_chat.py
```

`/reset` komutuyla oturumu sıfırlayabilirsiniz.

---

## Veritabanı

Varsayılan olarak SQLite kullanılır (`hairdresser.db`). PostgreSQL için:

```
DATABASE_URL=postgresql+asyncpg://user:password@localhost/hairdresser
```

> Şema değişikliklerinde tabloları yeniden oluşturmak için `hairdresser.db` dosyasını silin ve uygulamayı yeniden başlatın. Alembic ile migration yönetimi henüz eklenmemiştir.
