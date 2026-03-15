"""Tests for BookingFlow step validators and processors."""
import pytest

from conversation_flows.booking_flow import BookingFlow, _NAME_RE, _is_valid_turkish_phone


# ── Phone validation ───────────────────────────────────────────────────────────

class TestIsValidTurkishPhone:
    def test_valid_10_digit_05xx(self):
        assert _is_valid_turkish_phone("05321234567")

    def test_valid_10_digit_with_spaces(self):
        assert _is_valid_turkish_phone("0532 123 45 67")

    def test_valid_12_digit_905xx(self):
        assert _is_valid_turkish_phone("905321234567")

    def test_valid_12_digit_plus905xx(self):
        assert _is_valid_turkish_phone("+905321234567")

    def test_invalid_landline_istanbul(self):
        assert not _is_valid_turkish_phone("02125550000")

    def test_invalid_landline_ankara(self):
        assert not _is_valid_turkish_phone("03125550000")

    def test_invalid_too_short(self):
        assert not _is_valid_turkish_phone("0532123")

    def test_invalid_empty(self):
        assert not _is_valid_turkish_phone("")

    def test_invalid_letters(self):
        assert not _is_valid_turkish_phone("abcdefghij")

    def test_valid_formatted_with_dashes(self):
        assert _is_valid_turkish_phone("0532-123-45-67")


# ── Name regex validation ──────────────────────────────────────────────────────

class TestNameRegex:
    def test_valid_simple(self):
        assert _NAME_RE.match("Ahmet")

    def test_valid_full_name(self):
        assert _NAME_RE.match("Ahmet Yılmaz")

    def test_valid_turkish_chars(self):
        assert _NAME_RE.match("Şükrü Çelik")

    def test_valid_with_hyphen(self):
        assert _NAME_RE.match("Fatma-Nur")

    def test_valid_with_apostrophe(self):
        assert _NAME_RE.match("O'Brien")

    def test_invalid_starts_with_digit(self):
        assert not _NAME_RE.match("1Ahmet")

    def test_invalid_contains_digit(self):
        assert not _NAME_RE.match("Ahmet123")

    def test_invalid_empty(self):
        assert not _NAME_RE.match("")

    def test_invalid_single_char(self):
        # The second char-class requires ≥1 more char, so a single char fails the regex
        assert not _NAME_RE.match("A")


# ── Step processors ────────────────────────────────────────────────────────────

@pytest.fixture
def flow():
    return BookingFlow()


_EMPTY_INTENT = {"intent": "", "confidence": 0.0, "entities": {}}


class TestProcService:
    def test_valid_button_id(self, flow):
        ok, nxt, data = flow.process_step_input("select_service", "svc_0", _EMPTY_INTENT, {})
        assert ok
        assert nxt == "select_location"
        assert data["service"] == "Düğün Saç & Makyaj"

    def test_valid_button_id_second_service(self, flow):
        ok, nxt, data = flow.process_step_input("select_service", "svc_1", _EMPTY_INTENT, {})
        assert ok
        assert data["service"] == "Kına Saç & Makyaj"

    def test_valid_numeric_shortcut(self, flow):
        ok, nxt, data = flow.process_step_input("select_service", "1", _EMPTY_INTENT, {})
        assert ok
        assert data["service"] == "Düğün Saç & Makyaj"

    def test_valid_text_match(self, flow):
        ok, nxt, data = flow.process_step_input(
            "select_service", "nişan istiyorum",
            {"intent": "", "confidence": 0.0, "entities": {"service": "Nişan Saç & Makyaj"}}, {}
        )
        assert ok
        assert data["service"] == "Nişan Saç & Makyaj"

    def test_invalid_random_text(self, flow):
        ok, nxt, _ = flow.process_step_input("select_service", "bilmiyorum", _EMPTY_INTENT, {})
        assert not ok
        assert nxt == "select_service"

    def test_invalid_out_of_range_index(self, flow):
        ok, nxt, _ = flow.process_step_input("select_service", "svc_99", _EMPTY_INTENT, {})
        assert not ok


class TestProcLocation:
    def test_studio_button(self, flow):
        ok, nxt, data = flow.process_step_input("select_location", "studio", _EMPTY_INTENT, {})
        assert ok
        assert data["location_type"] == "studio"
        assert nxt == "select_branch"

    def test_hotel_text(self, flow):
        ok, nxt, data = flow.process_step_input("select_location", "otele", _EMPTY_INTENT, {})
        assert ok
        assert data["location_type"] == "hotel"
        assert nxt == "get_visit_address"

    def test_stüdyo_text(self, flow):
        ok, nxt, data = flow.process_step_input("select_location", "Stüdyoya", _EMPTY_INTENT, {})
        assert ok
        assert data["location_type"] == "studio"
        assert nxt == "select_branch"

    def test_out_of_city_button(self, flow):
        fd = {"service": "Düğün Saç & Makyaj"}
        ok, nxt, data = flow.process_step_input("select_location", "out_of_city", _EMPTY_INTENT, fd)
        assert ok
        assert data["location_type"] == "out_of_city"
        assert nxt == "get_visit_address"

    def test_out_of_city_text(self, flow):
        fd = {"service": "Düğün Saç & Makyaj"}
        ok, nxt, data = flow.process_step_input("select_location", "şehir dışı", _EMPTY_INTENT, fd)
        assert ok
        assert data["location_type"] == "out_of_city"
        assert nxt == "get_visit_address"

    def test_out_of_city_not_matched_by_hotel_keyword(self, flow):
        # "şehir dışı otel" should be out_of_city, not hotel
        fd = {"service": "Düğün Saç & Makyaj"}
        ok, nxt, data = flow.process_step_input("select_location", "şehir dışı otel", _EMPTY_INTENT, fd)
        assert ok
        assert data["location_type"] == "out_of_city"

    def test_out_of_city_blocked_for_non_ozel_gun(self, flow):
        # Profesyonel hizmette "şehir dışı" metni kabul edilmemeli
        fd = {"service": "Profesyonel Makyaj"}
        ok, nxt, _ = flow.process_step_input("select_location", "şehir dışı", _EMPTY_INTENT, fd)
        assert not ok
        assert nxt == "select_location"

    def test_invalid(self, flow):
        ok, nxt, _ = flow.process_step_input("select_location", "nereye", _EMPTY_INTENT, {})
        assert not ok
        assert nxt == "select_location"


class TestProcName:
    def test_valid_full_name(self, flow):
        ok, nxt, data = flow.process_step_input("get_name", "Ayşe Yılmaz", _EMPTY_INTENT, {})
        assert ok
        assert data["customer_name"] == "Ayşe Yılmaz"
        assert nxt == "get_phone"

    def test_invalid_single_word_name(self, flow):
        # Single word is rejected — full name (first + last) is required
        ok, nxt, _ = flow.process_step_input("get_name", "Mehmet", _EMPTY_INTENT, {})
        assert not ok
        assert nxt == "get_name"

    def test_invalid_single_char(self, flow):
        ok, _, _ = flow.process_step_input("get_name", "A", _EMPTY_INTENT, {})
        assert not ok

    def test_invalid_with_numbers(self, flow):
        ok, _, _ = flow.process_step_input("get_name", "Ahmet123", _EMPTY_INTENT, {})
        assert not ok

    def test_name_from_entity(self, flow):
        intent = {"intent": "provide_name", "confidence": 0.9, "entities": {"name": "Fatma Şahin"}}
        ok, _, data = flow.process_step_input("get_name", "benim adım fatma şahin", intent, {})
        assert ok
        assert data["customer_name"] == "Fatma Şahin"


class TestProcPhone:
    def test_valid_phone(self, flow):
        ok, nxt, data = flow.process_step_input("get_phone", "0532 123 45 67", _EMPTY_INTENT, {})
        assert ok
        assert nxt == "confirm"

    def test_valid_plus90(self, flow):
        ok, nxt, data = flow.process_step_input("get_phone", "+905321234567", _EMPTY_INTENT, {})
        assert ok

    def test_phone_use_wa_button(self, flow):
        ok, nxt, data = flow.process_step_input(
            "get_phone", "phone_use_wa", _EMPTY_INTENT,
            {"whatsapp_phone": "+90 532 123 45 67"}
        )
        assert ok
        assert nxt == "confirm"
        assert data["customer_phone"] == "+90 532 123 45 67"

    def test_phone_enter_new_button(self, flow):
        ok, nxt, data = flow.process_step_input("get_phone", "phone_enter_new", _EMPTY_INTENT, {})
        assert ok
        assert nxt == "get_phone"
        assert data.get("phone_prompted") is True

    def test_invalid_landline(self, flow):
        ok, _, _ = flow.process_step_input("get_phone", "02125550000", _EMPTY_INTENT, {})
        assert not ok


class TestProcConfirm:
    def test_evet(self, flow):
        ok, nxt, data = flow.process_step_input("confirm", "evet", _EMPTY_INTENT, {})
        assert ok
        assert nxt == "done"
        assert data["confirmed"] is True

    def test_button_confirm_yes(self, flow):
        ok, nxt, data = flow.process_step_input("confirm", "confirm_yes", _EMPTY_INTENT, {})
        assert ok
        assert data["confirmed"] is True

    def test_hayır(self, flow):
        ok, nxt, data = flow.process_step_input("confirm", "hayır", _EMPTY_INTENT, {})
        assert ok
        assert nxt == "done"
        assert data["confirmed"] is False

    def test_button_confirm_no(self, flow):
        ok, nxt, data = flow.process_step_input("confirm", "confirm_no", _EMPTY_INTENT, {})
        assert ok
        assert data["confirmed"] is False

    def test_affirmative_intent(self, flow):
        intent = {"intent": "affirmative", "confidence": 0.9, "entities": {}}
        ok, nxt, data = flow.process_step_input("confirm", "tabii ki", intent, {})
        assert ok
        assert data["confirmed"] is True

    def test_invalid_random(self, flow):
        ok, nxt, _ = flow.process_step_input("confirm", "belki", _EMPTY_INTENT, {})
        assert not ok
        assert nxt == "confirm"
