#!/usr/bin/env bash
set -euo pipefail

# ── Renkler ──────────────────────────────────────────────
G='\033[0;32m'; Y='\033[1;33m'; R='\033[0;31m'; B='\033[1;34m'; NC='\033[0m'
ok()    { echo -e " ${G}[OK]${NC}   $*"; }
info()  { echo -e " ${B}[INFO]${NC} $*"; }
warn()  { echo -e " ${Y}[UYARI]${NC} $*"; }
err()   { echo -e " ${R}[HATA]${NC} $*"; }

echo
echo " ================================================"
echo "   Izellik Makeup House - WhatsApp Chatbot"
echo " ================================================"
echo

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PID_FILE="$SCRIPT_DIR/.chatbot.pid"

# ─── Zaten calisiyor mu? ─────────────────────────────────
if [[ -f "$PID_FILE" ]]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        warn "Sunucu zaten calisiyor (PID: $OLD_PID). Once stop.sh calistirin."
        exit 1
    else
        rm -f "$PID_FILE"
    fi
fi

# ─── 1. .env kontrolu ────────────────────────────────────
if [[ ! -f ".env" ]]; then
    err ".env dosyasi bulunamadi!"
    echo
    echo "        .env.example dosyasini kopyalayip .env olarak kaydedin"
    echo "        ve API anahtarlarini girin."
    echo
    exit 1
fi
ok ".env dosyasi bulundu"

# ─── 2. Python kontrolu ──────────────────────────────────
PYTHON=""
for cmd in python3.13 python3.12 python3.11 python3 python; do
    if command -v "$cmd" &>/dev/null; then
        VER=$("$cmd" -c 'import sys; print(sys.version_info[:2])' 2>/dev/null || echo "(0, 0)")
        MAJ=$(echo "$VER" | tr -d '()' | cut -d',' -f1 | tr -d ' ')
        MIN=$(echo "$VER" | tr -d '()' | cut -d',' -f2 | tr -d ' ')
        if [[ "$MAJ" -eq 3 && "$MIN" -ge 11 && "$MIN" -le 13 ]]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [[ -z "$PYTHON" ]]; then
    err "Python 3.11-3.13 bulunamadi!"
    echo
    echo "        Python 3.14+ bazi kutuphaneler icin hazir paket sunmuyor."
    echo "        Python 3.12 veya 3.13 onerilir."
    echo
    if [[ "$(uname)" == "Darwin" ]]; then
        echo "        Mac: brew install python@3.13"
    else
        echo "        Ubuntu/Debian: sudo apt install python3.12"
        echo "        Fedora/RHEL:   sudo dnf install python3.12"
    fi
    echo
    exit 1
fi

PYVER=$("$PYTHON" --version 2>&1 | awk '{print $2}')
ok "Python $PYVER bulundu ($PYTHON)"

# ─── 3. Sanal ortam (venv) ───────────────────────────────
if [[ ! -f ".venv/bin/activate" ]]; then
    info "Sanal ortam olusturuluyor (.venv)..."
    "$PYTHON" -m venv .venv
    ok "Sanal ortam olusturuldu"
else
    ok "Sanal ortam mevcut: .venv"
fi

source ".venv/bin/activate"
ok "Sanal ortam aktiflestirildi"

# ─── 4. pip guncelle ─────────────────────────────────────
info "pip guncelleniyor..."
python -m pip install --upgrade pip -q --disable-pip-version-check
ok "pip guncellendi"

# ─── 5. Python kutuphanelerini kur ───────────────────────
info "Python kutuphaneleri kuruluyor..."
pip install -r requirements.txt -q --disable-pip-version-check || {
    err "Kutuphaneler yuklenemedi! requirements.txt kontrol edin."
    exit 1
}
ok "Python kutuphaneleri hazir"

# ─── 6. Admin UI build (Node.js varsa) ───────────────────
if [[ ! -f "admin-ui/dist/index.html" ]]; then
    if command -v node &>/dev/null; then
        NODE_VER=$(node --version)
        info "Admin UI derleniyor (Node $NODE_VER)..."
        (
            cd admin-ui
            npm install --silent 2>/dev/null || npm install
            npm run build
        ) && ok "Admin UI derlendi" || warn "Admin UI derlenemedi, devam ediliyor..."
    else
        warn "Node.js bulunamadi - Admin UI devre disi"
        warn "Node.js kurmak icin: https://nodejs.org/"
    fi
else
    ok "Admin UI mevcut"
fi

# ─── 7. ngrok kontrolu ve baslatma ───────────────────────
NGROK_URL=""
NGROK_PID=""
if command -v ngrok &>/dev/null; then
    info "ngrok baslatiliyor..."
    ngrok http 8000 --log=stdout > /tmp/ngrok-chatbot.log 2>&1 &
    NGROK_PID=$!
    # Tunnel acilmasini bekle (max 5 sn)
    for i in {1..10}; do
        sleep 0.5
        NGROK_URL=$(python3 -c "
import urllib.request, json
try:
    d = json.loads(urllib.request.urlopen('http://127.0.0.1:4040/api/tunnels', timeout=1).read())
    urls = [t['public_url'] for t in d.get('tunnels', []) if t['public_url'].startswith('https')]
    print(urls[0] if urls else '')
except: print('')
" 2>/dev/null || true)
        [[ -n "$NGROK_URL" ]] && break
    done
    if [[ -n "$NGROK_URL" ]]; then
        ok "ngrok tunnel actildi"
    else
        warn "ngrok URL alinamadi - manuel kontrol: http://127.0.0.1:4040"
    fi
else
    warn "ngrok bulunamadi - WhatsApp webhook icin gerekli"
    warn "Kurmak icin: https://ngrok.com/download"
fi

# ─── 8. Sunucuyu baslat ──────────────────────────────────
echo
echo " ================================================"
echo "  Sunucu baslatiliyor..."
echo "  Yerel  : http://localhost:8000"
echo "  Admin  : http://localhost:8000/admin-ui"
echo "  Docs   : http://localhost:8000/docs"
if [[ -n "$NGROK_URL" ]]; then
    echo "  Genel  : $NGROK_URL"
    echo "  Webhook: $NGROK_URL/webhook"
    echo
    echo "  Meta Developer Console'da webhook URL'ini guncelle:"
    echo "  $NGROK_URL/webhook"
fi
echo "  Dur    : ./stop.sh  veya  CTRL+C"
echo " ================================================"
echo

uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
UVICORN_PID=$!
echo "$UVICORN_PID" > "$PID_FILE"

cleanup() {
    echo
    info "Durduruluyor..."
    kill "$UVICORN_PID" 2>/dev/null || true
    pkill -P "$UVICORN_PID" 2>/dev/null || true
    [[ -n "$NGROK_PID" ]] && kill "$NGROK_PID" 2>/dev/null || true
    rm -f "$PID_FILE"
    ok "Sunucu durduruldu."
    exit 0
}
trap cleanup INT TERM

wait "$UVICORN_PID" || true
rm -f "$PID_FILE"
