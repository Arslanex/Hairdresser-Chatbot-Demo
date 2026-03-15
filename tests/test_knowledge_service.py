"""Tests for KnowledgeService and knowledge helper functions."""
import pytest

from services.knowledge_service import KnowledgeService, _format_working_days


# ── _format_working_days ───────────────────────────────────────────────────────

class TestFormatWorkingDays:
    def test_full_week_mon_to_sat(self):
        assert _format_working_days([0, 1, 2, 3, 4, 5]) == "Pazartesi–Cumartesi"

    def test_weekdays_mon_to_fri(self):
        assert _format_working_days([0, 1, 2, 3, 4]) == "Pazartesi–Cuma"

    def test_single_day(self):
        assert _format_working_days([3]) == "Perşembe"

    def test_non_consecutive(self):
        result = _format_working_days([1, 3, 5])
        assert result == "Salı, Perşembe, Cumartesi"

    def test_two_ranges(self):
        # Mon-Wed and Fri-Sat
        result = _format_working_days([0, 1, 2, 4, 5])
        assert result == "Pazartesi–Çarşamba, Cuma–Cumartesi"

    def test_empty_list(self):
        assert _format_working_days([]) == "Kapalı"

    def test_unsorted_input_is_sorted(self):
        # Same as [0,1,2,3,4] regardless of input order
        assert _format_working_days([4, 2, 0, 3, 1]) == "Pazartesi–Cuma"

    def test_all_seven_days(self):
        assert _format_working_days([0, 1, 2, 3, 4, 5, 6]) == "Pazartesi–Pazar"


# ── KnowledgeService.get_available_times ──────────────────────────────────────

class TestGetAvailableTimes:
    @pytest.fixture
    def ks(self):
        return KnowledgeService()

    def test_starts_at_working_hours_start(self, ks):
        times = ks.get_available_times()
        from config import settings
        assert times[0] == f"{settings.working_hours_start:02d}:00"

    def test_last_slot_before_working_hours_end(self, ks):
        times = ks.get_available_times()
        from config import settings
        # Last slot must be strictly before working_hours_end
        last_h, last_m = map(int, times[-1].split(":"))
        assert last_h < settings.working_hours_end

    def test_slots_are_30_minutes_apart(self, ks):
        times = ks.get_available_times()
        assert len(times) >= 2
        h1, m1 = map(int, times[0].split(":"))
        h2, m2 = map(int, times[1].split(":"))
        diff = (h2 * 60 + m2) - (h1 * 60 + m1)
        assert diff == 30

    def test_default_settings_count(self, ks):
        # Default: 09:00–19:00, 2 slots/hour × 10 hours = 20 slots
        times = ks.get_available_times()
        assert len(times) == 20

    def test_default_settings_boundaries(self, ks):
        times = ks.get_available_times()
        assert times[0] == "09:00"
        assert times[-1] == "18:30"

    def test_all_slots_valid_format(self, ks):
        import re
        for t in ks.get_available_times():
            assert re.fullmatch(r"\d{2}:\d{2}", t), f"Invalid format: {t}"


# ── KnowledgeService.get_staff_for_service ────────────────────────────────────

class TestGetStaffForService:
    @pytest.fixture
    def ks(self):
        return KnowledgeService()

    def test_known_service_returns_staff(self, ks):
        staff = ks.get_staff_for_service("Düğün Saç & Makyaj")
        assert len(staff) >= 1
        assert all("id" in s and "name" in s and "price_tl" in s for s in staff)

    def test_unknown_service_returns_empty(self, ks):
        assert ks.get_staff_for_service("Bilinmeyen Hizmet") == []

    def test_all_services_have_staff(self, ks):
        for svc in ks.get_services():
            staff = ks.get_staff_for_service(svc["name"])
            assert len(staff) > 0, f"No staff for service: {svc['name']}"
