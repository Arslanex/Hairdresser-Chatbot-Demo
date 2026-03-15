"""Tests for Turkish natural language date and time parser."""
import pytest
from datetime import date as real_date, timedelta
from unittest.mock import patch, MagicMock

import ai.date_time_parser as dtp
from ai.date_time_parser import parse_turkish_date, parse_turkish_time

# Fixed test date: Monday 2026-03-16
_FIXED_DATE = real_date(2026, 3, 16)


def _patch_today(fixed: real_date = _FIXED_DATE):
    """Context manager that freezes date.today() in the parser module."""
    mock = MagicMock(spec=real_date)
    mock.today.return_value = fixed
    mock.side_effect = real_date  # date(y, m, d) calls still work
    return patch.object(dtp, "date", mock)


# ── parse_turkish_date ─────────────────────────────────────────────────────────

class TestParseTurkishDate:
    def test_yarın_is_tomorrow(self):
        with _patch_today():
            result = parse_turkish_date("yarın")
        assert result == _FIXED_DATE + timedelta(days=1)

    def test_yarin_ascii(self):
        with _patch_today():
            result = parse_turkish_date("yarin")
        assert result == _FIXED_DATE + timedelta(days=1)

    def test_öbür_gün_is_day_after_tomorrow(self):
        with _patch_today():
            result = parse_turkish_date("öbür gün")
        assert result == _FIXED_DATE + timedelta(days=2)

    def test_n_gün_sonra(self):
        with _patch_today():
            result = parse_turkish_date("3 gün sonra")
        assert result == _FIXED_DATE + timedelta(days=3)

    def test_n_hafta_sonra(self):
        with _patch_today():
            result = parse_turkish_date("2 hafta sonra")
        assert result == _FIXED_DATE + timedelta(weeks=2)

    def test_haftaya_same_weekday(self):
        with _patch_today():
            result = parse_turkish_date("haftaya")
        assert result == _FIXED_DATE + timedelta(weeks=1)

    def test_next_weekday_cuma(self):
        # From Monday 2026-03-16, next "cuma" is 2026-03-20 (Friday=4)
        with _patch_today():
            result = parse_turkish_date("cuma")
        assert result is not None
        assert result.weekday() == 4  # Friday
        assert result > _FIXED_DATE

    def test_haftaya_salı(self):
        # "haftaya salı" from Monday → next Tuesday + ≥7 days
        with _patch_today():
            result = parse_turkish_date("haftaya salı")
        assert result is not None
        assert result.weekday() == 1  # Tuesday
        assert (result - _FIXED_DATE).days >= 7

    def test_explicit_date_slashes(self):
        with _patch_today():
            result = parse_turkish_date("20/06/2099")
        assert result == real_date(2099, 6, 20)

    def test_explicit_date_dots(self):
        with _patch_today():
            result = parse_turkish_date("20.06.2099")
        assert result == real_date(2099, 6, 20)

    def test_month_name_format(self):
        # "15 haziran" → June 15
        with _patch_today():
            result = parse_turkish_date("15 haziran")
        assert result is not None
        assert result.month == 6
        assert result.day == 15

    def test_past_date_returns_none(self):
        with _patch_today():
            result = parse_turkish_date("01/01/2020")
        assert result is None

    def test_today_returns_none(self):
        with _patch_today():
            result = parse_turkish_date(_FIXED_DATE.strftime("%d/%m/%Y"))
        assert result is None

    def test_nonsense_returns_none(self):
        result = parse_turkish_date("asdfjkl")
        assert result is None

    def test_empty_string_returns_none(self):
        result = parse_turkish_date("")
        assert result is None


# ── parse_turkish_time ─────────────────────────────────────────────────────────

class TestParseTurkishTime:
    def test_explicit_hhmm(self):
        assert parse_turkish_time("14:30") == "14:30"

    def test_explicit_hhmm_morning(self):
        assert parse_turkish_time("09:00") == "09:00"

    def test_öğlen(self):
        assert parse_turkish_time("öğlen") == "12:00"

    def test_öğle(self):
        assert parse_turkish_time("öğle") == "12:00"

    def test_sabah_10(self):
        assert parse_turkish_time("sabah 10") == "10:00"

    def test_sabah_9(self):
        assert parse_turkish_time("sabah 9") == "09:00"

    def test_akşam_6(self):
        assert parse_turkish_time("akşam 6") == "18:00"

    def test_akşam_7(self):
        # 19:00 is outside working hours (end is exclusive), so returns None
        assert parse_turkish_time("akşam 7") is None

    def test_öğleden_sonra_3(self):
        assert parse_turkish_time("öğleden sonra 3") == "15:00"

    def test_öğleden_sonra_2_buçuk(self):
        assert parse_turkish_time("öğleden sonra 2 buçuk") == "14:30"

    def test_saat_10(self):
        assert parse_turkish_time("saat 10") == "10:00"

    def test_bare_integer_in_business_hours(self):
        # "14" → 14:00
        assert parse_turkish_time("14") == "14:00"

    def test_bare_integer_early_am_shifted(self):
        # "3" → 3 < 9 → add 12 → 15:00
        assert parse_turkish_time("3") == "15:00"

    def test_outside_business_hours_returns_none(self):
        # 22:00 is outside working hours
        assert parse_turkish_time("22:00") is None

    def test_midnight_returns_none(self):
        assert parse_turkish_time("00:00") is None

    def test_nonsense_returns_none(self):
        assert parse_turkish_time("yarın") is None

    def test_buçuk(self):
        # "10 buçuk" → 10:30
        assert parse_turkish_time("10 buçuk") == "10:30"

    def test_word_number_buçuk(self):
        # "iki buçuk" → 2 < 9 → add 12 → 14:30
        assert parse_turkish_time("iki buçuk") == "14:30"
