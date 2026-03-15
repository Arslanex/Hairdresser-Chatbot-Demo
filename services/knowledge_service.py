"""Knowledge service providing static business information for İzellik Makeup House."""
from __future__ import annotations

from config import settings

# ─── Static data ──────────────────────────────────────────────────────────────

SERVICES: list[dict] = [
    # Özel Gün (6) — price depends on artist; 9.000 TL is starting price
    {"id": "dugun_sac_makyaj",  "name": "Düğün Saç & Makyaj",     "category": "Özel Gün",    "duration_minutes": 180, "base_price_tl": 9000},
    {"id": "kina_sac_makyaj",   "name": "Kına Saç & Makyaj",      "category": "Özel Gün",    "duration_minutes": 180, "base_price_tl": 9000},
    {"id": "nisan_sac_makyaj",  "name": "Nişan Saç & Makyaj",     "category": "Özel Gün",    "duration_minutes": 180, "base_price_tl": 9000},
    {"id": "dugun_turban",      "name": "Düğün Türban Tasarım",    "category": "Özel Gün",    "duration_minutes": 180, "base_price_tl": 9000},
    {"id": "kina_turban",       "name": "Kına Türban Tasarım",     "category": "Özel Gün",    "duration_minutes": 180, "base_price_tl": 9000},
    {"id": "nisan_turban",      "name": "Nişan Türban Tasarım",    "category": "Özel Gün",    "duration_minutes": 180, "base_price_tl": 9000},
    # Profesyonel (2)
    {"id": "profesyonel_sac",   "name": "Profesyonel Saç & Makyaj","category": "Profesyonel", "duration_minutes": 90,  "base_price_tl": 5000},
    {"id": "profesyonel_makyaj","name": "Profesyonel Makyaj",      "category": "Profesyonel", "duration_minutes": 90,  "base_price_tl": 5000},
    # Diğer (2)
    {"id": "tirnak",            "name": "Tırnak İşlemleri",        "category": "Diğer",       "duration_minutes": 60,  "base_price_tl": 0},
    {"id": "sac_bakim",         "name": "Saç Bakım Hizmetleri",    "category": "Diğer",       "duration_minutes": 60,  "base_price_tl": 0},
]

# Two studio branches
BRANCHES: dict[str, dict] = {
    "gaziantep": {
        "id": "gaziantep",
        "name": "İzellik Makeup House Gaziantep",
        "city": "Gaziantep",
        "address": "Şahinbey, Gaziantep",
        "phone": "+90 549 272 0101",
        "phone_2": "+90 540 272 3434",
        "maps_url": "https://maps.google.com/?q=İzellik+Makeup+House+Gaziantep",
    },
    "istanbul": {
        "id": "istanbul",
        "name": "İzellik Makeup House İstanbul",
        "city": "İstanbul",
        "address": "Şişli, İstanbul",
        "phone": "+90 543 272 0101",
        "phone_2": "+90 550 272 3434",
        "maps_url": "https://maps.google.com/?q=İzellik+Makeup+House+Istanbul",
    },
}

# Makeup artists
# branch_ids: which branches this artist serves
# price_tl: stüdyo/otel fiyatı (starting); out_of_city_price_tl: şehir dışı sabit paket fiyatı
_ALL_STAFF: list[dict] = [
    # Gaziantep sanatçıları
    {"id": "izel",     "name": "İzel",     "title": "Baş Makeup Artist", "instagram": "izellikmua",       "branch_ids": ["gaziantep"], "price_tl": 15000, "price_label": "15.000–20.000 TL", "out_of_city_price_tl": 50000},
    {"id": "merve",    "name": "Merve",    "title": "Makeup Artist",     "instagram": "merveeorta",       "branch_ids": ["gaziantep"], "price_tl": 10000, "price_label": "10.000–13.000 TL", "out_of_city_price_tl": 40000},
    {"id": "dicle",    "name": "Dicle",    "title": "Makeup Artist",     "instagram": "diclebayysal",     "branch_ids": ["gaziantep"], "price_tl": 10000, "price_label": "10.000–13.000 TL", "out_of_city_price_tl": 40000},
    {"id": "irem",     "name": "İrem",     "title": "Makeup Artist",     "instagram": "iremmuua",         "branch_ids": ["gaziantep"], "price_tl": 9000,  "price_label": "9.000–11.000 TL",  "out_of_city_price_tl": 35000},
    # İstanbul sanatçıları
    {"id": "gizem",    "name": "Gizem",    "title": "Makeup Artist",     "instagram": "gizem_mua",        "branch_ids": ["istanbul"],  "price_tl": 9000,  "price_label": "9.000–11.000 TL",  "out_of_city_price_tl": 35000},
    {"id": "neslihan", "name": "Neslihan", "title": "Makeup Artist",     "instagram": "neslihan.bozbaş",  "branch_ids": ["istanbul"],  "price_tl": 9000,  "price_label": "9.000–11.000 TL",  "out_of_city_price_tl": 35000},
    {"id": "sena",     "name": "Sena",     "title": "Makeup Artist",     "instagram": "senaaamua",        "branch_ids": ["istanbul"],  "price_tl": 9000,  "price_label": "~9.000 TL",         "out_of_city_price_tl": 30000},
]

# Grouped views (used by STAFF_BY_SERVICE fallback and get_business_info)
_OZEL_GUN_STAFF = _ALL_STAFF  # all artists do özel gün
# Genel hizmetler: Dicle ve Merve sadece özel gün alıyor
_GENEL_STAFF: list[dict] = [s for s in _ALL_STAFF if s["id"] not in ("merve", "dicle")]

def _staff_for_branch(staff_list: list[dict], branch_id: str) -> list[dict]:
    """Filter staff list to those serving the given branch (empty branch_id = no filter)."""
    if not branch_id:
        return staff_list
    return [s for s in staff_list if branch_id in s.get("branch_ids", [])]

def _sehir_disi_staff(branch_id: str = "") -> list[dict]:
    """Şehir dışı staff: artists with out_of_city_price_tl, optionally filtered by branch."""
    base = [s for s in _ALL_STAFF if "out_of_city_price_tl" in s]
    if branch_id:
        base = [s for s in base if branch_id in s.get("branch_ids", [])]
    return [
        {**s, "price_tl": s["out_of_city_price_tl"],
         "price_label": f"{s['out_of_city_price_tl']:,}".replace(",", ".") + " TL"}
        for s in base
    ]

STAFF_BY_SERVICE: dict[str, list[dict]] = {
    "Düğün Saç & Makyaj":       _OZEL_GUN_STAFF,
    "Kına Saç & Makyaj":        _OZEL_GUN_STAFF,
    "Nişan Saç & Makyaj":       _OZEL_GUN_STAFF,
    "Düğün Türban Tasarım":     _OZEL_GUN_STAFF,
    "Kına Türban Tasarım":      _OZEL_GUN_STAFF,
    "Nişan Türban Tasarım":     _OZEL_GUN_STAFF,
    "Profesyonel Saç & Makyaj": _GENEL_STAFF,
    "Profesyonel Makyaj":       _GENEL_STAFF,
    "Tırnak İşlemleri":         _GENEL_STAFF,
    "Saç Bakım Hizmetleri":     _GENEL_STAFF,
}

# Hotel visit: pricing quoted separately (0 = no automatic surcharge)
HOTEL_VISIT_SURCHARGE_TL = 0

# Extra guest (nedime / davetli) surcharges per additional person
GUEST_SURCHARGE_TL = 5000           # stüdyo veya otel ziyaret
OUT_OF_CITY_GUEST_SURCHARGE_TL = 7000  # şehir dışı otel

# Optional ek saç eklentisi
EK_SAC_TL = 4000

LOCATION_TYPES: list[dict] = [
    {"id": "studio",      "label": "Stüdyo",          "desc": "Salonumuza gelin (Gaziantep veya İstanbul)"},
    {"id": "hotel",       "label": "Otel (Şehir İçi)", "desc": "Otelinizde hazırlanın"},
    {"id": "out_of_city", "label": "Şehir Dışı Otel",  "desc": "Şehir dışı — paket fiyatı uygulanır"},
]

_DAY_NAMES: dict[int, str] = {
    0: "Pazartesi", 1: "Salı", 2: "Çarşamba",
    3: "Perşembe",  4: "Cuma", 5: "Cumartesi", 6: "Pazar",
}


def _format_working_days(days: list[int]) -> str:
    days = sorted(set(days))
    if not days:
        return "Kapalı"
    ranges: list[tuple[int, int]] = []
    start = prev = days[0]
    for d in days[1:]:
        if d == prev + 1:
            prev = d
        else:
            ranges.append((start, prev))
            start = prev = d
    ranges.append((start, prev))
    parts = []
    for s, e in ranges:
        parts.append(_DAY_NAMES[s] if s == e else f"{_DAY_NAMES[s]}–{_DAY_NAMES[e]}")
    return ", ".join(parts)


def get_default_prompt_sections() -> dict[str, str]:
    """Return the 4 default prompt sections auto-generated from static data."""

    def _fmt(p: int) -> str:
        return f"{p:,}".replace(",", ".") if p else "—"

    behavior = (
        f"Sen {settings.business_name} makyaj ve güzellik salonu için samimi ve yardımsever bir asistansın.\n"
        "Yalnızca salonun hizmetleri, randevular, çalışma saatleri, fiyatlar ve konum hakkındaki sorulara yanıt veriyorsun.\n"
        "Sıcak, özlü ve profesyonel bir dil kullan. Her zaman Türkçe yanıtla. Cevapları kısa ve net tut.\n"
        "Kullanıcıya karşı nazik ve anlayışlı ol; konu salon dışına çıkarsa kibarca salon konularına yönlendir."
    )

    branch_lines = "\n".join(
        f"  • {b['city']}: {b['address']} | Tel: {b['phone']} / {b['phone_2']}"
        for b in BRANCHES.values()
    )
    working_days_str = _format_working_days(settings.working_days)
    business = (
        f"## İşletme Bilgileri\n"
        f"İsim: {settings.business_name}\n\n"
        f"Şubeler:\n{branch_lines}\n\n"
        f"Çalışma Saatleri: {working_days_str} "
        f"{settings.working_hours_start:02d}:00–{settings.working_hours_end:02d}:00"
    )

    service_lines = "\n".join(
        f"  • {s['name']} ({s['category']}): {s['duration_minutes']} dk"
        + (f", {_fmt(s['base_price_tl'])} TL'den" if s["base_price_tl"] else "")
        for s in SERVICES
    )
    services = (
        "## Hizmetler ve Fiyatlar\n"
        f"{service_lines}\n\n"
        f"Nedime/davetli ek ücreti: {_fmt(GUEST_SURCHARGE_TL)} TL/kişi "
        f"(şehir dışı {_fmt(OUT_OF_CITY_GUEST_SURCHARGE_TL)} TL/kişi).\n"
        f"Ek saç: {_fmt(EK_SAC_TL)} TL."
    )

    def _staff_block(staff_list: list[dict], city: str) -> str:
        lines = "\n".join(
            f"  • {s['name']} ({s['title']}): {s.get('price_label', _fmt(s['price_tl']) + ' TL')}"
            + (f" | @{s['instagram']}" if s.get("instagram") else "")
            + (f" | Şehir dışı: {_fmt(s['out_of_city_price_tl'])} TL" if s.get("out_of_city_price_tl") else "")
            for s in staff_list
        )
        return f"{city}:\n{lines}"

    gzt_staff = [s for s in _ALL_STAFF if "gaziantep" in s.get("branch_ids", [])]
    ist_staff = [s for s in _ALL_STAFF if "istanbul" in s.get("branch_ids", [])]
    staff = (
        "## Makeup Artist Ekibi\n"
        f"{_staff_block(gzt_staff, 'Gaziantep')}\n\n"
        f"{_staff_block(ist_staff, 'İstanbul')}\n\n"
        "Not: Merve ve Dicle yalnızca özel gün (gelin/kına/nişan) randevusu alır."
    )

    return {
        "prompt_behavior": behavior,
        "prompt_business": business,
        "prompt_services": services,
        "prompt_staff": staff,
    }


class KnowledgeService:
    """Provides static knowledge about İzellik Makeup House."""

    def get_services(self) -> list[dict]:
        return SERVICES

    def get_branches(self) -> dict[str, dict]:
        return BRANCHES

    def get_staff_for_service(self, service_name: str) -> list[dict]:
        return STAFF_BY_SERVICE.get(service_name, [])

    def get_staff_for_service_and_location(
        self, service_name: str, location_type: str = "studio", branch_id: str = ""
    ) -> list[dict]:
        """Return staff for the given service + location + branch combination.

        - Şehir dışı otel: only artists with out_of_city_price_tl (fixed package price).
        - branch_id filters to artists serving that branch.
        """
        if location_type == "out_of_city":
            service = next((s for s in SERVICES if s["name"] == service_name), None)
            if service and service.get("category") == "Özel Gün":
                return _sehir_disi_staff(branch_id)
        base = STAFF_BY_SERVICE.get(service_name, [])
        return _staff_for_branch(base, branch_id)

    def get_location_types(self) -> list[dict]:
        return LOCATION_TYPES

    def get_working_hours(self) -> str:
        return (
            f"{_format_working_days(settings.working_days)}: "
            f"{settings.working_hours_start:02d}:00–{settings.working_hours_end:02d}:00"
        )

    def get_address(self) -> str:
        return settings.business_address

    def get_available_times(self) -> list[str]:
        """30-minute slots from working_hours_start to working_hours_end (exclusive)."""
        times: list[str] = []
        hour = settings.working_hours_start
        minute = 0
        while hour < settings.working_hours_end:
            times.append(f"{hour:02d}:{minute:02d}")
            minute += 30
            if minute >= 60:
                minute = 0
                hour += 1
        return times

    def get_business_info(self) -> str:
        def _fmt(p: int) -> str:
            return f"{p:,}".replace(",", ".") if p else "—"

        services_text = "\n".join(
            f"  • {s['name']}: {s['duration_minutes']} dk, {_fmt(s['base_price_tl'])} TL'den"
            for s in SERVICES
        )
        staff_text = "\n".join(
            f"  • {s['name']} ({s['title']}): {s.get('price_label', _fmt(s['price_tl']) + ' TL')}"
            for s in _OZEL_GUN_STAFF
        )
        branch_lines = "\n".join(
            f"  📍 {b['city']}: {b['address']}  Tel: {b['phone']} / {b['phone_2']}"
            for b in BRANCHES.values()
        )
        return (
            f"*{settings.business_name}*\n\n"
            f"Şubelerimiz:\n{branch_lines}\n"
            f"Çalışma Saatleri: {self.get_working_hours()}\n\n"
            f"Hizmetlerimiz:\n{services_text}\n\n"
            f"Makeup Artist Ekibimiz:\n{staff_text}\n\n"
            "Not: Merve ve Dicle yalnızca özel gün (gelin/kına/nişan) randevusu alır. "
            "Gaziantep şehir dışı: İzel 50.000 TL, Merve/Dicle 40.000 TL. "
            "İstanbul şehir dışı: Gizem/Neslihan 35.000 TL, Sena 30.000 TL. "
            "Nedime/davetli ek ücreti: 5.000 TL/kişi (şehir dışı 7.000 TL/kişi)."
        )
