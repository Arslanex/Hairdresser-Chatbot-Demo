"""Tests for config.py validators."""
import pytest

from config import Settings


class TestParseWorkingDays:
    def test_json_string_full_week(self):
        assert Settings.parse_working_days("[0,1,2,3,4,5]") == [0, 1, 2, 3, 4, 5]

    def test_json_string_weekdays_only(self):
        assert Settings.parse_working_days("[0,1,2,3,4]") == [0, 1, 2, 3, 4]

    def test_json_string_single_day(self):
        assert Settings.parse_working_days("[5]") == [5]

    def test_list_passthrough(self):
        assert Settings.parse_working_days([0, 1, 2]) == [0, 1, 2]

    def test_json_string_coerces_to_int(self):
        result = Settings.parse_working_days("[0,1,2]")
        assert all(isinstance(d, int) for d in result)

    def test_invalid_json_raises(self):
        with pytest.raises(Exception):
            Settings.parse_working_days("not-json")

    def test_json_object_raises(self):
        with pytest.raises(Exception):
            Settings.parse_working_days('{"key": "value"}')
