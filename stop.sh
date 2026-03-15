#!/usr/bin/env bash
set -euo pipefail

G='\033[0;32m'; R='\033[0;31m'; B='\033[1;34m'; NC='\033[0m'
ok()   { echo -e " ${G}[OK]${NC}   $*"; }
info() { echo -e " ${B}[INFO]${NC} $*"; }
err()  { echo -e " ${R}[HATA]${NC} $*"; }

echo
echo " ================================================"
echo "   Izellik Makeup House - Sunucu Durdur"
echo " ================================================"
echo

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/.chatbot.pid"

kill_pid() {
    local pid=$1
    info "Surec durduruluyor (PID: $pid)..."
    kill "$pid" 2>/dev/null || true
    # Alt surecler (watchfiles / reload worker)
    pkill -P "$pid" 2>/dev/null || true
    # 5 saniye bekle
    for i in {1..10}; do
        kill -0 "$pid" 2>/dev/null || { ok "Sunucu durduruldu."; return 0; }
        sleep 0.5
    done
    # Hala calısıyorsa zorla kapat
    kill -9 "$pid" 2>/dev/null || true
    ok "Sunucu zorla durduruldu."
}

# ─── PID dosyasindan kapat ───────────────────────────────
if [[ -f "$PID_FILE" ]]; then
    PID=$(cat "$PID_FILE")
    rm -f "$PID_FILE"
    if [[ -n "$PID" ]] && kill -0 "$PID" 2>/dev/null; then
        kill_pid "$PID"
    else
        info "Surec zaten durmus (eski PID: $PID)"
    fi
    exit 0
fi

# ─── PID dosyasi yoksa port 8000'den bul ─────────────────
info "PID dosyasi bulunamadi, port 8000 aranıyor..."

if command -v lsof &>/dev/null; then
    PID=$(lsof -ti tcp:8000 2>/dev/null | head -1 || true)
elif command -v fuser &>/dev/null; then
    PID=$(fuser 8000/tcp 2>/dev/null | awk '{print $1}' || true)
else
    PID=""
fi

if [[ -n "$PID" ]]; then
    kill_pid "$PID"
else
    info "Calisan sunucu bulunamadi."
fi
