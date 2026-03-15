"""Tests for module-level helper functions in ai_service.py."""
import pytest

from services.ai_service import (
    _extract_response_text,
    _format_wa_phone,
    _is_button_id,
    _resolve_back_step,
)


# ── _is_button_id ──────────────────────────────────────────────────────────────

class TestIsButtonId:
    # select_service
    def test_service_valid_id(self):
        assert _is_button_id("select_service", "svc_0")

    def test_service_valid_id_multi_digit(self):
        assert _is_button_id("select_service", "svc_12")

    def test_service_free_text(self):
        assert not _is_button_id("select_service", "saç boyama istiyorum")

    def test_service_numeric_shortcut(self):
        # "1" is handled by _proc_service but NOT a button ID
        assert not _is_button_id("select_service", "1")

    # select_location
    def test_location_studio(self):
        assert _is_button_id("select_location", "studio")

    def test_location_hotel(self):
        assert _is_button_id("select_location", "hotel")

    def test_location_turkish_stüdyo(self):
        assert _is_button_id("select_location", "stüdyo")

    def test_location_free_text(self):
        assert not _is_button_id("select_location", "eve gelin")

    # select_staff
    def test_staff_valid_id(self):
        assert _is_button_id("select_staff", "staff_izel")

    def test_staff_free_text(self):
        assert not _is_button_id("select_staff", "uzman değiştirmek istiyorum")

    # confirm
    def test_confirm_yes(self):
        assert _is_button_id("confirm", "confirm_yes")

    def test_confirm_no(self):
        assert _is_button_id("confirm", "confirm_no")

    def test_confirm_evet_free_text(self):
        # "evet" is NOT a button ID — intent classifier should handle it
        assert not _is_button_id("confirm", "evet")

    def test_confirm_hayır_free_text(self):
        assert not _is_button_id("confirm", "hayır")

    # steps without structured IDs
    def test_free_text_step_always_false(self):
        assert not _is_button_id("select_date", "yarın")
        assert not _is_button_id("get_name", "Ahmet Yılmaz")
        assert not _is_button_id("get_phone", "0532 000 00 00")


# ── _resolve_back_step ─────────────────────────────────────────────────────────

class TestResolveBackStep:
    def test_service_from_later_step(self):
        # At select_staff (3), asking for service (0) → jump back
        assert _resolve_back_step("provide_service", "select_staff") == "select_service"

    def test_service_from_confirm(self):
        # At confirm (8), asking for service (0) → jump back
        assert _resolve_back_step("provide_service", "confirm") == "select_service"

    def test_service_at_same_step(self):
        # At select_service (0), provide_service (0) → no jump (same index)
        assert _resolve_back_step("provide_service", "select_service") is None

    def test_service_from_earlier_step(self):
        # At select_location (1), requesting service (0) → valid back-jump
        assert _resolve_back_step("provide_service", "select_location") == "select_service"

    def test_location_from_select_staff(self):
        assert _resolve_back_step("provide_location", "select_staff") == "select_location"

    def test_staff_from_select_date(self):
        assert _resolve_back_step("provide_staff", "select_date") == "select_staff"

    def test_date_from_select_time(self):
        assert _resolve_back_step("provide_date", "select_time") == "select_date"

    def test_time_from_get_name(self):
        assert _resolve_back_step("provide_time", "get_name") == "select_time"

    def test_date_from_same_step(self):
        # At select_date (4), provide_date (4) → no jump
        assert _resolve_back_step("provide_date", "select_date") is None

    def test_time_from_select_date(self):
        # At select_date (4), provide_time (5) → target is LATER, no jump
        assert _resolve_back_step("provide_time", "select_date") is None

    def test_unknown_intent(self):
        assert _resolve_back_step("booking_request", "select_staff") is None

    def test_empty_intent(self):
        assert _resolve_back_step("", "confirm") is None

    def test_cancel_intent(self):
        # cancel_booking is not in _INTENT_TO_STEP
        assert _resolve_back_step("cancel_booking", "confirm") is None


# ── _format_wa_phone ───────────────────────────────────────────────────────────

class TestFormatWaPhone:
    def test_12_digit_90_prefix(self):
        assert _format_wa_phone("905321234567") == "+90 532 123 45 67"

    def test_11_digit_0_prefix(self):
        assert _format_wa_phone("05321234567") == "0532 123 45 67"

    def test_already_plus_prefix(self):
        result = _format_wa_phone("+1234567890")
        assert result.startswith("+")

    def test_unknown_format_adds_plus(self):
        result = _format_wa_phone("1234567890")
        assert result == "+1234567890"


# ── _extract_response_text ─────────────────────────────────────────────────────

class TestExtractResponseText:
    def test_text_type(self):
        resp = {"type": "text", "text": {"body": "Merhaba!"}}
        assert _extract_response_text(resp) == "Merhaba!"

    def test_multi_type(self):
        resp = {
            "type": "multi",
            "messages": [
                {"type": "text", "text": {"body": "İlk mesaj."}},
                {"type": "text", "text": {"body": "İkinci mesaj."}},
            ]
        }
        result = _extract_response_text(resp)
        assert "İlk mesaj." in result
        assert "İkinci mesaj." in result

    def test_multi_skips_non_text(self):
        resp = {
            "type": "multi",
            "messages": [
                {"type": "interactive", "interactive": {"body": {"text": "ignored"}}},
                {"type": "text", "text": {"body": "Alındı."}},
            ]
        }
        assert _extract_response_text(resp) == "Alındı."

    def test_interactive_type(self):
        resp = {
            "type": "interactive",
            "interactive": {"body": {"text": "Hizmet seçin:"}}
        }
        assert _extract_response_text(resp) == "Hizmet seçin:"

    def test_unknown_type(self):
        assert _extract_response_text({"type": "unknown"}) == ""

    def test_empty_dict(self):
        assert _extract_response_text({}) == ""
