"""Multi-step booking flow – comprehensive version.

Steps (with branching):
  select_service
    → select_location          (Stüdyo / Otel / Şehir Dışı Otel)
        → get_visit_address    (only when location == hotel or out_of_city)
    → select_staff             (based on chosen service + location)
    → select_date              (smart Turkish NL parser)
    → select_time              (smart Turkish NL parser + buttons)
    → get_guest_count
    → get_name
    → get_phone
    → confirm
    → done
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime

logger = logging.getLogger(__name__)

from ai.date_time_parser import parse_turkish_date, parse_turkish_time
from config import settings
from services.knowledge_service import (
    HOTEL_VISIT_SURCHARGE_TL,
    GUEST_SURCHARGE_TL,
    OUT_OF_CITY_GUEST_SURCHARGE_TL,
    BRANCHES,
    SERVICES,
    KnowledgeService,
)

_knowledge = KnowledgeService()

# All possible step IDs (order used only for reference)
FLOW_STEPS = [
    "select_service",
    "select_location",
    "select_branch",       # conditional (only when location == studio)
    "get_visit_address",   # conditional (only hotel / out_of_city)
    "select_staff",
    "select_date",
    "select_time",
    "get_guest_count",
    "get_name",
    "get_phone",
    "confirm",
    "done",
]

_TURKISH_DAYS: dict[int, str] = {
    0: "Pazartesi", 1: "Salı", 2: "Çarşamba",
    3: "Perşembe",  4: "Cuma", 5: "Cumartesi", 6: "Pazar",
}

# Name: at least one letter, only letters (incl. Turkish), spaces, hyphens, apostrophes
_NAME_RE = re.compile(
    r"^[a-zA-ZÇçĞğİıÖöŞşÜü][a-zA-ZÇçĞğİıÖöŞşÜü\s'\-]+$"
)

# Minimum name length (still enforced alongside regex)
_MIN_NAME_LEN = 2

# Turkish character → ASCII for fuzzy name/location matching (e.g. "ayse" → "ayse" matches "Ayşe")
_TURKISH_TO_ASCII = str.maketrans(
    "ıİğĞüÜşŞöÖçÇ",
    "iIgGuUsSoOcC",
)


def _normalize_turkish_for_match(text: str) -> str:
    """Normalize Turkish chars then lowercase so 'ayse' matches 'Ayşe', 'istanbul' matches 'İstanbul'."""
    return text.translate(_TURKISH_TO_ASCII).lower()


def _is_valid_turkish_phone(raw: str) -> bool:
    """Accept Turkish mobile numbers in 05xx (10-digit) or +90/905x (12-digit) format."""
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits.startswith("05"):
        return True
    if len(digits) == 12 and digits.startswith("905"):
        return True
    return False


class BookingFlow:
    """Generates WhatsApp messages and processes user input for each booking step."""

    # ─── Step message factory ─────────────────────────────────────────────────

    def get_current_step_message(self, step: str, flow_data: dict) -> dict:
        """Return the WhatsApp payload for *step*."""
        handlers = {
            "select_service":    self._msg_select_service,
            "select_location":   self._msg_select_location,
            "select_branch":     self._msg_select_branch,
            "get_visit_address": self._msg_get_visit_address,
            "select_staff":      self._msg_select_staff,
            "select_date":       self._msg_select_date,
            "select_time":       self._msg_select_time,
            "get_guest_count":   self._msg_get_guest_count,
            "get_name":          self._msg_get_name,
            "get_phone":         self._msg_get_phone,
            "confirm":           self._msg_confirm,
            "done":              self._msg_done,
        }
        fn = handlers.get(step)
        if fn is None:
            return _text("Randevu işlemi tamamlandı.")
        return fn(flow_data)

    # ─── Input processor dispatcher ──────────────────────────────────────────

    def process_step_input(
        self,
        step: str,
        user_input: str,
        intent: dict,
        flow_data: dict,
    ) -> tuple[bool, str, dict]:
        """Validate *user_input* for *step*.

        Returns ``(is_valid, next_step, updated_flow_data)``.
        """
        updated = dict(flow_data)
        processors = {
            "select_service":    self._proc_service,
            "select_location":   self._proc_location,
            "select_branch":     self._proc_branch,
            "get_visit_address": self._proc_visit_address,
            "select_staff":      self._proc_staff,
            "select_date":       self._proc_date,
            "select_time":       self._proc_time,
            "get_guest_count":   self._proc_guest_count,
            "get_name":          self._proc_name,
            "get_phone":         self._proc_phone,
            "confirm":           self._proc_confirm,
        }
        fn = processors.get(step)
        if fn is None:
            logger.warning("[STEP] unknown step=%r — skipping", step)
            return False, step, updated
        is_valid, next_step, result_data = fn(user_input, intent, updated)
        entities = {k: v for k, v in intent.get("entities", {}).items() if v}
        logger.debug(
            "[STEP:%-20s] input=%r entities=%s → %s next=%s",
            step, user_input[:60], entities if entities else "{}",
            "VALID" if is_valid else "INVALID", next_step,
        )
        return is_valid, next_step, result_data

    # ─── Validation helpers ───────────────────────────────────────────────────

    def validate_date(self, date_str: str) -> bool:
        """Return True if *date_str* is a future working day."""
        parsed = parse_turkish_date(date_str)
        if parsed is None:
            # Fallback: try explicit format
            parsed = _try_parse_explicit_date(date_str)
        if parsed is None or parsed <= date.today():
            return False
        return parsed.weekday() in settings.working_days

    def validate_time(self, time_str: str) -> bool:
        available = _knowledge.get_available_times()
        try:
            h, m = map(int, time_str.strip().split(":"))
            return f"{h:02d}:{m:02d}" in available
        except (ValueError, AttributeError):
            return False

    # ═══════════════════════════════════════════════════════════════════════════
    # Message builders
    # ═══════════════════════════════════════════════════════════════════════════

    def _msg_select_service(self, _: dict) -> dict:
        services = _knowledge.get_services()
        cat_map: dict[str, list[tuple[int, dict]]] = {}
        for i, s in enumerate(services):
            cat = s.get("category", "Hizmetler")
            cat_map.setdefault(cat, []).append((i, s))

        sections = []
        for cat_name, items in cat_map.items():
            rows = []
            for i, s in items:
                price = s["base_price_tl"]
                price_str = f"{price:,}".replace(",", ".") if price else "—"
                rows.append({
                    "id": f"svc_{i}",
                    "title": s["name"][:24],
                    "description": (
                        f"{s['duration_minutes']} dk · {price_str} TL'den"
                        if price else f"{s['duration_minutes']} dk"
                    ),
                })
            sections.append({"title": cat_name, "rows": rows})

        return _interactive_list(
            header="Hizmet Seçimi",
            body="Almak istediğiniz hizmeti seçin:",
            button_label="Hizmet seç",
            sections=sections,
        )

    def _msg_select_location(self, flow_data: dict) -> dict:
        service = flow_data.get("service", "")
        # Show "Şehir Dışı Otel" only for özel gün services
        service_obj = next((s for s in SERVICES if s["name"] == service), None)
        is_ozel_gun = bool(service_obj and service_obj.get("category") == "Özel Gün")
        location_types = [
            lt for lt in _knowledge.get_location_types()
            if lt["id"] != "out_of_city" or is_ozel_gun
        ]
        buttons = [_btn(lt["id"], lt["label"]) for lt in location_types]
        return _interactive_buttons(
            body=(
                f"*{service}* için hizmet nerede verilsin?\n\n"
                + "\n".join(f"• *{lt['label']}:* {lt['desc']}" for lt in location_types)
            ),
            buttons=buttons,
        )

    def _msg_select_branch(self, _: dict) -> dict:
        branches = list(BRANCHES.values())
        buttons = [_btn(b["id"], b["city"]) for b in branches]
        branch_lines = "\n".join(
            f"📍 *{b['name']}*\n   {b['address']}\n   📞 {b['phone']}"
            for b in branches
        )
        return _interactive_buttons(
            body=f"Hangi şubemize gelmek istersiniz?\n\n{branch_lines}",
            buttons=buttons,
        )

    def _msg_get_visit_address(self, flow_data: dict) -> dict:
        if flow_data.get("location_type") == "out_of_city":
            return _text(
                "Hazırlık yapılacak otelin adını ve şehrini paylaşır mısınız? 🌆\n\n"
                "_(Örnek: Swissôtel İstanbul, Beşiktaş)_"
            )
        return _text(
            "Otel hazırlığı için otel adını veya adresini paylaşır mısınız?\n\n"
            "_(Örnek: Sheraton Gaziantep Oteli)_"
        )

    def _msg_select_staff(self, flow_data: dict) -> dict:
        service = flow_data.get("service", "")
        location_type = flow_data.get("location_type", "studio")
        branch_id = flow_data.get("branch_id", "")
        staff_list = _knowledge.get_staff_for_service_and_location(service, location_type, branch_id)

        if not staff_list:
            return _text("Uzman seçimi şu an mevcut değil, devam ediyoruz.")

        def _staff_desc(s: dict) -> str:
            price = s.get("price_label") or f"{s['price_tl']:,}".replace(",", ".") + " TL'den"
            ig = s.get("instagram", "")
            ig_part = f" instagram.com/{ig}" if ig else ""
            return f"{price}{ig_part}"[:72]  # WhatsApp list row description max

        rows = [
            {"id": f"staff_{s['id']}", "title": s["name"], "description": _staff_desc(s)}
            for s in staff_list
        ]
        location_note = ""
        if location_type == "out_of_city":
            location_note = "\n_(Şehir dışı paket fiyatı)_"
        return _interactive_list(
            header="Uzman Seçimi",
            body=f"*{service}* için hangi uzmanla çalışmak istersiniz?{location_note}",
            button_label="Uzman seç",
            sections=[{"title": "Uzmanlarımız", "rows": rows}],
        )

    def _msg_select_date(self, flow_data: dict) -> dict:
        working_day_names = [_TURKISH_DAYS[d] for d in sorted(settings.working_days)]
        days_text = ", ".join(working_day_names)
        today = date.today()
        return _text(
            "Randevu için tarih belirleyelim.\n\n"
            f"Çalışma günlerimiz: *{days_text}*\n\n"
            "Şu ifadelerden birini kullanabilirsiniz:\n"
            "• *yarın*, *öbür gün*\n"
            "• *bu cuma*, *haftaya salı*, *gelecek çarşamba*\n"
            "• *2 gün sonra*, *1 hafta sonra*\n"
            f"• Tarih formatı: *GG/AA/YYYY*  _(örn. {today.strftime('%d/%m/%Y')})_"
        )

    def _msg_select_time(self, flow_data: dict) -> dict:
        available = _knowledge.get_available_times()
        service = flow_data.get("service", "")
        date_display = flow_data.get("appointment_date_display", "")
        staff_name = flow_data.get("staff_name", "")

        # WhatsApp interactive list: total rows across ALL sections ≤ 10.
        # We show representative on-the-hour slots (max 3 per period = 9 total)
        # and list every available slot in the body so the user can type any time.
        _MAX_PER_PERIOD = 3

        morning   = [t for t in available if int(t.split(":")[0]) < 12]
        afternoon = [t for t in available if 12 <= int(t.split(":")[0]) < 17]
        evening   = [t for t in available if int(t.split(":")[0]) >= 17]

        def _sample(slots: list[str]) -> list[str]:
            """Return at most _MAX_PER_PERIOD evenly-spaced slots."""
            if len(slots) <= _MAX_PER_PERIOD:
                return slots
            step = len(slots) / _MAX_PER_PERIOD
            return [slots[int(i * step)] for i in range(_MAX_PER_PERIOD)]

        def _rows(slots: list[str]) -> list[dict]:
            return [
                {"id": f"time_{t.replace(':', '')}", "title": t[:24], "description": ""}
                for t in slots
            ]

        sections = []
        if morning:
            sections.append({"title": "Sabah", "rows": _rows(_sample(morning))})
        if afternoon:
            sections.append({"title": "Öğleden Sonra", "rows": _rows(_sample(afternoon))})
        if evening:
            sections.append({"title": "Akşam", "rows": _rows(_sample(evening))})

        all_times_str = "  ".join(available)
        body = (
            f"Hizmet: *{service}*\n"
            f"Tarih: *{date_display}*\n"
            + (f"Uzman: *{staff_name}*\n" if staff_name else "")
            + f"\nMüsait saatler: _{all_times_str}_\n\n"
            "Listeden bir saat seçin *ya da* dilediğiniz saati yazın:\n"
            "• *öğleden sonra 3*, *sabah 10*, *14:30*, *akşam 6*"
        )
        return _interactive_list(
            header="Saat Seçimi",
            body=body,
            button_label="Saat seç",
            sections=sections,
        )

    def _msg_get_guest_count(self, flow_data: dict) -> dict:
        location_type = flow_data.get("location_type", "studio")
        if location_type == "out_of_city":
            extra_note = f"\n_Ek kişi başı {OUT_OF_CITY_GUEST_SURCHARGE_TL:,}".replace(",", ".") + " TL eklenir._"
        else:
            extra_note = f"\n_Ek kişi başı {GUEST_SURCHARGE_TL:,}".replace(",", ".") + " TL eklenir._"
        return _text(
            "Hazırlanacak kişi sayısını öğrenebilir miyim? 👥\n\n"
            "_(Gelin dahil toplam kişi sayısını yazın, örn: 1, 3, 5)_"
            + extra_note
        )

    def _msg_get_name(self, _: dict) -> dict:
        return _text("Teşekkürler! Randevunuzu kayıt edebilmem için lütfen *ad ve soyadınızı* girin.\nÖrnek: Ayşe Yılmaz")

    def _msg_get_phone(self, flow_data: dict) -> dict:
        if flow_data.get("phone_prompted"):
            return _text(
                "Telefon numaranızı girin:\n"
                "_(Örnek: 0532 123 45 67)_"
            )
        wa_phone = flow_data.get("whatsapp_phone", "")
        if wa_phone:
            return _interactive_buttons(
                body=(
                    "Son adım! Telefon numaranızı onaylayın.\n\n"
                    f"WhatsApp numaranız: *{wa_phone}*\n\n"
                    "Bu numarayı kullanabilir veya farklı bir numara girebilirsiniz."
                ),
                buttons=[
                    _btn("phone_use_wa", "✅ Bu numarayı kullan"),
                    _btn("phone_enter_new", "📝 Farklı numara"),
                ],
            )
        return _text(
            "Son adım — sizi arayabilmemiz için telefon numaranızı alabilir miyim?\n"
            "_(Örnek: 0532 123 45 67)_"
        )

    def _msg_confirm(self, flow_data: dict) -> dict:
        location_type = flow_data.get("location_type", "studio")
        if location_type == "studio":
            branch_id = flow_data.get("branch_id", "")
            branch = BRANCHES.get(branch_id, {})
            location_line = f"📍 {branch.get('name', '')} – {branch.get('address', '')}"
        elif location_type == "out_of_city":
            visit_addr = flow_data.get("visit_address", "")
            location_line = f"📍 Şehir Dışı Otel: {visit_addr}"
        else:
            visit_addr = flow_data.get("visit_address", "")
            location_line = f"📍 Otel: {visit_addr}"

        guest_count = flow_data.get("guest_count", 1)
        extra_guests = max(0, guest_count - 1)
        hotel_surcharge, guest_surcharge = _surcharge_breakdown(flow_data)
        total_surcharge = hotel_surcharge + guest_surcharge
        base_price = flow_data.get("staff_price_tl", 0)
        price = base_price + total_surcharge
        price_str = f"{price:,}".replace(",", ".")
        surcharge_parts = []
        if hotel_surcharge:
            surcharge_parts.append(f"+{f'{hotel_surcharge:,}'.replace(',', '.')} TL ziyaret")
        if guest_surcharge and extra_guests:
            per = guest_surcharge // extra_guests
            surcharge_parts.append(
                f"+{f'{guest_surcharge:,}'.replace(',', '.')} TL "
                f"({extra_guests} nedime × {f'{per:,}'.replace(',', '.')} TL)"
            )
        surcharge_note = "  (" + ", ".join(surcharge_parts) + ")" if surcharge_parts else ""

        staff_name = flow_data.get("staff_name", "")
        staff_title = flow_data.get("staff_title", "")
        staff_line = (
            f"Uzman  : {staff_name}"
            + (f" ({staff_title})" if staff_title else "")
            + "\n"
            if staff_name
            else ""
        )
        summary = (
            "───────────────────\n"
            "💄 *RANDEVU ÖZETİ*\n"
            "───────────────────\n"
            f"Hizmet : {flow_data.get('service', '')}\n"
            f"{staff_line}"
            f"Kişi   : {flow_data.get('guest_count', 1)}\n"
            f"Tarih  : {flow_data.get('appointment_date_display', '')}\n"
            f"Saat   : {flow_data.get('appointment_time', '')}\n"
            f"{location_line}\n"
            f"Ad     : {flow_data.get('customer_name', '')}\n"
            f"Tel    : {flow_data.get('customer_phone', '')}\n"
            f"Ücret  : {price_str} TL{surcharge_note}\n"
            "───────────────────\n\n"
            "Bu bilgiler doğru mu?"
        )
        return _interactive_buttons(
            body=summary,
            buttons=[_btn("confirm_yes", "✅ Evet, Onayla"), _btn("confirm_no", "❌ Hayır, İptal")],
        )

    def _msg_done(self, _: dict) -> dict:
        return _text("Randevu işlemi tamamlandı.")

    # ═══════════════════════════════════════════════════════════════════════════
    # Input processors
    # ═══════════════════════════════════════════════════════════════════════════

    def _proc_service(self, raw: str, intent: dict, data: dict) -> tuple[bool, str, dict]:
        services = _knowledge.get_services()
        lower = raw.lower().strip()

        # list-reply id: "svc_0", "svc_2" …
        m = re.fullmatch(r"svc_(\d+)", lower)
        if m:
            idx = int(m.group(1))
            if 0 <= idx < len(services):
                data["service"] = services[idx]["name"]
                return True, "select_location", data

        # numeric shortcut
        try:
            idx = int(lower) - 1
            if 0 <= idx < len(services):
                data["service"] = services[idx]["name"]
                return True, "select_location", data
        except ValueError:
            pass

        # text / entity match (with Turkish→ASCII so "sac kesimi" matches "Saç Kesimi")
        candidate = intent.get("entities", {}).get("service", "") or raw
        candidate_norm = _normalize_turkish_for_match(candidate)
        for svc in services:
            name_norm = _normalize_turkish_for_match(svc["name"])
            if name_norm in candidate_norm or candidate_norm in name_norm:
                data["service"] = svc["name"]
                return True, "select_location", data

        return False, "select_service", data

    def _proc_location(self, raw: str, intent: dict, data: dict) -> tuple[bool, str, dict]:
        lower = raw.lower().strip()
        # Longer keys first so "şehir dışı otel" is matched before "otel"
        location_map = [
            ("out_of_city",  ("out_of_city", "Şehir Dışı Otel")),
            ("şehir dışı",   ("out_of_city", "Şehir Dışı Otel")),
            ("şehir disi",   ("out_of_city", "Şehir Dışı Otel")),
            ("sehir disi",   ("out_of_city", "Şehir Dışı Otel")),
            ("sehir dışı",   ("out_of_city", "Şehir Dışı Otel")),
            ("studio",       ("studio",      "Stüdyo")),
            ("stüdyo",       ("studio",      "Stüdyo")),
            ("stüdyoya",     ("studio",      "Stüdyo")),
            ("hotel",        ("hotel",       "Otel")),
            ("otel",         ("hotel",       "Otel")),
            ("otele",        ("hotel",       "Otel")),
        ]
        for key, (loc_id, label) in location_map:
            if key in lower:
                # Şehir dışı yalnızca özel gün hizmetleri için geçerlidir
                if loc_id == "out_of_city":
                    service_obj = next((s for s in SERVICES if s["name"] == data.get("service", "")), None)
                    if not (service_obj and service_obj.get("category") == "Özel Gün"):
                        continue
                data["location_type"] = loc_id
                data["location_label"] = label
                if loc_id == "studio":
                    return True, "select_branch", data
                else:  # hotel or out_of_city
                    return True, "get_visit_address", data
        return False, "select_location", data

    def _proc_branch(self, raw: str, intent: dict, data: dict) -> tuple[bool, str, dict]:
        lower_norm = _normalize_turkish_for_match(raw.strip())
        for branch_id, branch in BRANCHES.items():
            city_norm = _normalize_turkish_for_match(branch["city"])
            if (lower_norm == _normalize_turkish_for_match(branch_id)
                    or city_norm in lower_norm
                    or lower_norm in city_norm):
                data["branch_id"] = branch_id
                data["branch_name"] = branch["name"]
                data["branch_address"] = branch["address"]
                return True, "select_staff", data

        return False, "select_branch", data

    def _proc_visit_address(self, raw: str, intent: dict, data: dict) -> tuple[bool, str, dict]:
        # Accept anything ≥ 10 chars as a valid address
        addr = raw.strip()
        if len(addr) >= 10:
            data["visit_address"] = addr
            return True, "select_staff", data
        return False, "get_visit_address", data

    def _proc_staff(self, raw: str, intent: dict, data: dict) -> tuple[bool, str, dict]:
        service = data.get("service", "")
        location_type = data.get("location_type", "studio")
        branch_id = data.get("branch_id", "")
        staff_list = _knowledge.get_staff_for_service_and_location(service, location_type, branch_id)
        lower = raw.lower().strip()

        # list-reply id: "staff_ahmet"
        m = re.fullmatch(r"staff_(\w+)", lower)
        if m:
            sid = m.group(1)
            for s in staff_list:
                if s["id"] == sid:
                    _save_staff(data, s)
                    return True, "select_date", data

        # numeric shortcut
        try:
            idx = int(lower) - 1
            if 0 <= idx < len(staff_list):
                _save_staff(data, staff_list[idx])
                return True, "select_date", data
        except ValueError:
            pass

        # name match (with Turkish→ASCII normalization so "ayse" matches "Ayşe")
        lower_norm = _normalize_turkish_for_match(raw)
        for s in staff_list:
            name_norm = _normalize_turkish_for_match(s["name"])
            if name_norm in lower_norm or lower_norm in name_norm:
                _save_staff(data, s)
                return True, "select_date", data

        # No staff defined for this service — use service base price as fallback
        if not staff_list:
            base_price = next(
                (s["base_price_tl"] for s in SERVICES if s["name"] == data.get("service")),
                0,
            )
            data.setdefault("staff_id", "")
            data.setdefault("staff_name", "")
            data.setdefault("staff_title", "")
            data.setdefault("staff_price_tl", base_price)
            return True, "select_date", data

        return False, "select_staff", data

    def _proc_date(self, raw: str, intent: dict, data: dict) -> tuple[bool, str, dict]:
        # Try NL parser first, then explicit entity, then raw
        entity_date = intent.get("entities", {}).get("date", "")
        for candidate in (raw, entity_date):
            if not candidate:
                continue
            parsed = parse_turkish_date(candidate)
            if parsed is None:
                parsed = _try_parse_explicit_date(candidate)
            if parsed and parsed > date.today() and parsed.weekday() in settings.working_days:
                data["appointment_date"] = parsed.strftime("%Y-%m-%d")
                data["appointment_date_display"] = (
                    f"{parsed.strftime('%d/%m/%Y')} {_TURKISH_DAYS[parsed.weekday()]}"
                )
                return True, "select_time", data

        return False, "select_date", data

    def _proc_time(self, raw: str, intent: dict, data: dict) -> tuple[bool, str, dict]:
        lower = raw.lower().strip()
        available = _knowledge.get_available_times()

        # list-reply id: "time_1030"
        m = re.fullmatch(r"time_(\d{4})", lower)
        if m:
            formatted = f"{m.group(1)[:2]}:{m.group(1)[2:]}"
            if formatted in available:
                data["appointment_time"] = formatted
                return True, "get_guest_count", data

        # Try NL parser
        parsed_time = parse_turkish_time(raw)
        if parsed_time and parsed_time in available:
            data["appointment_time"] = parsed_time
            return True, "get_guest_count", data

        # Try entity
        entity_time = intent.get("entities", {}).get("time", "")
        if entity_time:
            entity_parsed = parse_turkish_time(entity_time)
            if entity_parsed and entity_parsed in available:
                data["appointment_time"] = entity_parsed
                return True, "get_guest_count", data
            if entity_parsed:
                parsed_time = entity_parsed

        # Nearest-slot fallback: if parsed time is close to a slot, accept
        if parsed_time:
            nearest = _nearest_slot(parsed_time, available)
            if nearest:
                data["appointment_time"] = nearest
                return True, "get_guest_count", data

        return False, "select_time", data

    def _proc_guest_count(self, raw: str, intent: dict, data: dict) -> tuple[bool, str, dict]:
        m = re.search(r"\d+", raw.strip())
        if m:
            count = int(m.group())
            if 1 <= count <= 20:
                data["guest_count"] = count
                return True, "get_name", data
        return False, "get_guest_count", data

    def _proc_name(self, raw: str, intent: dict, data: dict) -> tuple[bool, str, dict]:
        name = (intent.get("entities", {}).get("name", "") or raw).strip()
        # Require at least two words (first + last name) and only valid letters
        if len(name) >= _MIN_NAME_LEN and _NAME_RE.match(name) and " " in name:
            data["customer_name"] = name
            return True, "get_phone", data
        return False, "get_name", data

    def _proc_phone(self, raw: str, intent: dict, data: dict) -> tuple[bool, str, dict]:
        lower = raw.lower().strip()

        # "Use WhatsApp number" button
        if lower == "phone_use_wa":
            wa_phone = data.get("whatsapp_phone", "")
            if wa_phone:
                data["customer_phone"] = wa_phone
                data.pop("phone_prompted", None)
                return True, "confirm", data

        # "Enter different number" button — set flag, stay at same step to show plain prompt
        if lower == "phone_enter_new":
            data["phone_prompted"] = True
            return True, "get_phone", data

        # Actual phone number
        phone = (intent.get("entities", {}).get("phone", "") or raw).strip()
        if _is_valid_turkish_phone(phone):
            data["customer_phone"] = phone
            data.pop("phone_prompted", None)
            return True, "confirm", data
        return False, "get_phone", data

    def _proc_confirm(self, raw: str, intent: dict, data: dict) -> tuple[bool, str, dict]:
        lower = raw.lower().strip()
        _YES = {"evet", "yes", "tamam", "ok", "olur", "onayla", "confirm_yes", "kabul", "doğru", "dogru"}
        _NO  = {"hayır", "hayir", "no", "iptal", "cancel", "confirm_no", "vazgeç", "vazgec", "istemiyorum"}

        if lower in _YES or intent.get("intent") == "affirmative":
            data["confirmed"] = True
            return True, "done", data
        if lower in _NO or intent.get("intent") == "negative":
            data["confirmed"] = False
            return True, "done", data

        return False, "confirm", data


# ─── helpers ──────────────────────────────────────────────────────────────────

def _text(body: str) -> dict:
    return {"type": "text", "text": {"body": body}}


def _btn(btn_id: str, title: str) -> dict:
    return {"type": "reply", "reply": {"id": btn_id, "title": title[:20]}}


def _interactive_buttons(body: str, buttons: list[dict]) -> dict:
    return {
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body},
            "action": {"buttons": buttons[:3]},  # WhatsApp max = 3
        },
    }


def _interactive_list(
    header: str,
    body: str,
    button_label: str,
    sections: list[dict],
) -> dict:
    return {
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": header},
            "body": {"text": body},
            "footer": {"text": settings.business_name},
            "action": {
                "button": button_label,
                "sections": sections,
            },
        },
    }


def _save_staff(data: dict, staff: dict) -> None:
    data["staff_id"] = staff["id"]
    data["staff_name"] = staff["name"]
    data["staff_title"] = staff["title"]
    data["staff_price_tl"] = staff["price_tl"]


def _surcharge_breakdown(flow_data: dict) -> tuple[int, int]:
    """Return (hotel_surcharge, guest_surcharge) separately."""
    location_type = flow_data.get("location_type", "studio")
    hotel_surcharge = HOTEL_VISIT_SURCHARGE_TL if location_type == "hotel" else 0
    extra_guests = max(0, flow_data.get("guest_count", 1) - 1)
    if extra_guests:
        per_person = OUT_OF_CITY_GUEST_SURCHARGE_TL if location_type == "out_of_city" else GUEST_SURCHARGE_TL
        guest_surcharge = extra_guests * per_person
    else:
        guest_surcharge = 0
    return hotel_surcharge, guest_surcharge


def _surcharge(flow_data: dict) -> int:
    h, g = _surcharge_breakdown(flow_data)
    return h + g


def _try_parse_explicit_date(text: str) -> date | None:
    text = text.strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d.%m.%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _nearest_slot(time_str: str, available: list[str]) -> str | None:
    """Return the closest available slot to *time_str*, within 30 minutes."""
    try:
        h, m = map(int, time_str.split(":"))
        t_mins = h * 60 + m
    except ValueError:
        return None
    best: str | None = None
    best_diff = 31  # accept within 30 minutes
    for slot in available:
        sh, sm = map(int, slot.split(":"))
        diff = abs(sh * 60 + sm - t_mins)
        if diff < best_diff:
            best_diff = diff
            best = slot
    return best
