"""Turkish natural language date and time parser.

Supports expressions like:
  Dates:  yarın, haftaya cuma, gelecek salı, 2 gün sonra, 15/03/2026, 15 mart
  Times:  öğlen, öğleden sonra 3, sabah 10, akşam 7, 14:30, 2 buçuk, saat 5
"""
from __future__ import annotations

import re
from datetime import date, timedelta

# Turkish weekday name → Python weekday int (0=Monday … 6=Sunday)
TURKISH_DAYS: dict[str, int] = {
    "pazartesi": 0,
    "salı": 1, "sali": 1,
    "çarşamba": 2, "carsamba": 2, "çarsamba": 2,
    "perşembe": 3, "persembe": 3,
    "cuma": 4,
    "cumartesi": 5,
    "pazar": 6,
}

TURKISH_MONTHS: dict[str, int] = {
    "ocak": 1,
    "şubat": 2, "subat": 2,
    "mart": 3,
    "nisan": 4,
    "mayıs": 5, "mayis": 5,
    "haziran": 6,
    "temmuz": 7,
    "ağustos": 8, "agustos": 8,
    "eylül": 9, "eylul": 9,
    "ekim": 10,
    "kasım": 11, "kasim": 11,
    "aralık": 12, "aralik": 12,
}

WORD_NUMBERS: dict[str, int] = {
    "on iki": 12, "on bir": 11, "on": 10,
    "dokuz": 9,
    "sekiz": 8,
    "yedi": 7,
    "altı": 6, "alti": 6,
    "beş": 5, "bes": 5,
    "dört": 4, "dort": 4,
    "üç": 3, "uc": 3, "üc": 3,
    "iki": 2,
    "bir": 1,
}

_BUSINESS_START = 9   # used for AM/PM disambiguation (hours < 9 → add 12)


# ─── helpers ──────────────────────────────────────────────────────────────────

def _next_weekday(from_date: date, weekday: int) -> date:
    """Earliest date strictly after *from_date* with the given weekday."""
    days_ahead = (weekday - from_date.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return from_date + timedelta(days=days_ahead)


def _extract_int(text: str) -> int | None:
    """Parse the first integer from *text*, checking digit strings then word numbers."""
    m = re.search(r"\d+", text)
    if m:
        return int(m.group())
    for word, num in WORD_NUMBERS.items():
        if word in text:
            return num
    return None


def _in_business(h: int, mn: int = 0) -> bool:
    """True when h:mn falls within configured working hours."""
    from config import settings  # lazy import avoids any potential circular issues
    return _BUSINESS_START <= h < settings.working_hours_end


def _fmt(h: int, mn: int = 0) -> str | None:
    return f"{h:02d}:{mn:02d}" if _in_business(h, mn) else None


# ─── public API ───────────────────────────────────────────────────────────────

def parse_turkish_date(text: str) -> date | None:
    """Parse a Turkish natural-language date expression into a :class:`date`.

    Returns ``None`` if the expression cannot be interpreted or the resolved
    date is not strictly in the future.
    """
    t = text.lower().strip()
    today = date.today()

    # ── fixed keywords ───────────────────────────────────────────────────────
    if re.search(r"\byarın\b|\byarin\b", t):
        return today + timedelta(days=1)

    if re.search(r"\böbür\b|\bobur\b", t):
        return today + timedelta(days=2)

    # ── "X gün/hafta sonra [gün adı]" ────────────────────────────────────────
    # Extract number (digit or word) before gün/hafta sonra
    def _extract_offset(text: str, unit: str) -> int | None:
        m = re.search(rf"(\d+)\s*{unit}\s*sonra", text)
        if m:
            return int(m.group(1))
        for word, num in WORD_NUMBERS.items():
            if re.search(rf"\b{word}\b\s*{unit}\s*sonra", text):
                return num
        return None

    gun_offset = _extract_offset(t, "gün")
    if gun_offset is not None:
        anchor = today + timedelta(days=gun_offset)
        # Check if a weekday is also mentioned → find next occurrence from anchor
        for day_name, day_num in sorted(TURKISH_DAYS.items(), key=lambda x: -len(x[0])):
            if re.search(rf"\b{day_name}\b", t):
                return _next_weekday(anchor - timedelta(days=1), day_num)
        return anchor

    hafta_offset = _extract_offset(t, "hafta")
    if hafta_offset is not None:
        anchor = today + timedelta(weeks=hafta_offset)
        # Check if a weekday is also mentioned → find next occurrence from anchor
        for day_name, day_num in sorted(TURKISH_DAYS.items(), key=lambda x: -len(x[0])):
            if re.search(rf"\b{day_name}\b", t):
                return _next_weekday(anchor - timedelta(days=1), day_num)
        return anchor

    # ── weekday detection ────────────────────────────────────────────────────
    found_day: int | None = None
    for day_name, day_num in sorted(TURKISH_DAYS.items(), key=lambda x: -len(x[0])):
        if re.search(rf"\b{day_name}\b", t):
            found_day = day_num
            break

    if found_day is not None:
        # "haftaya", "gelecek", "önümüzdeki" → strictly ≥ 7 days away
        if re.search(r"\bhaftaya\b|\bgelecek\b|\bönümüzdeki\b|\bonumuzdeki\b", t):
            candidate = _next_weekday(today, found_day)
            if (candidate - today).days < 7:
                candidate += timedelta(weeks=1)
            return candidate
        # bare weekday or "bu [gün]" → next occurrence (could be 1–6 days away)
        return _next_weekday(today, found_day)

    # ── bare "haftaya" (no day name) → same weekday next week ────────────────
    if re.search(r"\bhaftaya\b", t):
        return today + timedelta(weeks=1)

    # ── explicit date formats ─────────────────────────────────────────────────
    m = re.search(r"(\d{1,2})[/\.\-](\d{1,2})[/\.\-](\d{4})", t)
    if m:
        try:
            d = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            return d if d > today else None
        except ValueError:
            pass

    # "15 ocak" style
    for month_name, month_num in sorted(TURKISH_MONTHS.items(), key=lambda x: -len(x[0])):
        m = re.search(rf"(\d{{1,2}})\s+{month_name}", t)
        if m:
            try:
                d = date(today.year, month_num, int(m.group(1)))
                if d <= today:
                    d = date(today.year + 1, month_num, int(m.group(1)))
                return d
            except ValueError:
                pass

    return None


def parse_turkish_time(text: str) -> str | None:
    """Parse a Turkish natural-language time expression into ``'HH:MM'`` format.

    Returns ``None`` if the time cannot be parsed or falls outside business
    hours (09:00–18:30).
    """
    t = text.lower().strip()

    # ── bare öğlen / öğle ────────────────────────────────────────────────────
    if re.fullmatch(r"öğle[n]?|ogle[n]?", t):
        return "12:00"

    # ── explicit HH:MM ───────────────────────────────────────────────────────
    m = re.search(r"\b(\d{1,2}):(\d{2})\b", t)
    if m:
        return _fmt(int(m.group(1)), int(m.group(2)))

    # ── X buçuk → X:30 ───────────────────────────────────────────────────────
    m = re.search(r"(\d{1,2})\s*buçuk|(\d{1,2})\s*bucuk", t)
    if not m:
        # word form: "iki buçuk"
        for word, num in WORD_NUMBERS.items():
            if re.search(rf"{word}\s*(buçuk|bucuk)", t):
                h = num
                if re.search(r"öğleden sonra|ogleden sonra", t) and h < 12:
                    h += 12
                elif h < _BUSINESS_START:
                    h += 12
                return _fmt(h, 30)
    if m:
        h = int(m.group(1) or m.group(2))
        if re.search(r"öğleden sonra|ogleden sonra", t) and h < 12:
            h += 12
        elif h < _BUSINESS_START:
            h += 12
        return _fmt(h, 30)

    # ── çeyrek geçe X / X çeyrek geçe → X:15 ────────────────────────────────
    m = re.search(r"çeyrek\s*geçe\s*(\d{1,2})|(\d{1,2})\s*çeyrek\s*geçe", t)
    if m:
        h = int(m.group(1) or m.group(2))
        if h < _BUSINESS_START:
            h += 12
        return _fmt(h, 15)

    # ── çeyrek kala X → (X-1):45 ─────────────────────────────────────────────
    m = re.search(r"çeyrek\s*kala\s*(\d{1,2})", t)
    if m:
        h = int(m.group(1))
        if h < _BUSINESS_START:
            h += 12
        return _fmt(h - 1, 45)

    # ── öğleden sonra X ──────────────────────────────────────────────────────
    if re.search(r"öğleden sonra|ogleden sonra", t):
        remainder = re.sub(r"öğleden\s*sonra|ogleden\s*sonra", "", t)
        h = _extract_int(remainder)
        if h is not None:
            if h < 12:
                h += 12
            return _fmt(h)

    # ── öğleden önce X ───────────────────────────────────────────────────────
    if re.search(r"öğleden önce|ogleden once", t):
        remainder = re.sub(r"öğleden\s*önce|ogleden\s*once", "", t)
        h = _extract_int(remainder)
        if h is not None and _BUSINESS_START <= h < 12:
            return _fmt(h)

    # ── sabah X ───────────────────────────────────────────────────────────────
    if re.search(r"\bsabah\b", t):
        h = _extract_int(t.replace("sabah", ""))
        if h is not None and _BUSINESS_START <= h < 12:
            return _fmt(h)

    # ── akşam X ───────────────────────────────────────────────────────────────
    if re.search(r"\bakşam\b|\baksam\b", t):
        remainder = re.sub(r"\bakşam\b|\baksam\b", "", t)
        h = _extract_int(remainder)
        if h is not None:
            if h <= 7:
                h += 12
            return _fmt(h)

    # ── öğlen + context (e.g. "öğlen 1 buçuk" already handled above) ─────────
    if re.search(r"\böğle[n]?\b|\bogle[n]?\b", t):
        return "12:00"

    # ── saat X ────────────────────────────────────────────────────────────────
    m = re.search(r"\bsaat\s*(\d{1,2})\b", t)
    if m:
        h = int(m.group(1))
        if h < _BUSINESS_START:
            h += 12
        return _fmt(h)

    # ── "Xde / X'de / Xda / X'da" ────────────────────────────────────────────
    m = re.search(r"(\d{1,2})\s*['\s]?(?:de|da)\b", t)
    if m:
        h = int(m.group(1))
        if h < _BUSINESS_START:
            h += 12
        return _fmt(h)

    # ── bare integer (last resort) ────────────────────────────────────────────
    m = re.fullmatch(r"(\d{1,2})", t)
    if m:
        h = int(m.group(1))
        if h < _BUSINESS_START:
            h += 12
        return _fmt(h)

    return None
