"""Tests de TimeManager — état temporel de session (logique pure, sans DB)."""
from __future__ import annotations

from PySide6.QtCore import QDate

from LarcSuperviseur.views.core.time_manager import TimeManager


class TestTimeManager:
    def test_defaults(self):
        tm = TimeManager()
        assert tm.current_period == "day"
        assert tm.term_id == 0
        assert tm.term_label == ""

    def test_period_dates_day(self):
        tm = TimeManager()
        today = QDate.currentDate().toString("yyyy-MM-dd")
        assert tm.period_dates() == (today, today)

    def test_period_dates_week(self):
        tm = TimeManager()
        tm.current_period = "week"
        start, end = tm.period_dates()
        s, e = QDate.fromString(start, "yyyy-MM-dd"), QDate.fromString(end, "yyyy-MM-dd")
        assert s.dayOfWeek() == 1  # lundi
        assert s.addDays(6) == e

    def test_period_dates_month(self):
        tm = TimeManager()
        tm.current_period = "month"
        d = tm.current_date
        start, end = tm.period_dates()
        assert start == QDate(d.year(), d.month(), 1).toString("yyyy-MM-dd")
        assert end == QDate(d.year(), d.month(), d.daysInMonth()).toString("yyyy-MM-dd")

    def test_period_dates_year(self):
        tm = TimeManager()
        tm.current_period = "year"
        d = tm.current_date
        start, end = tm.period_dates()
        assert start == QDate(d.year(), 1, 1).toString("yyyy-MM-dd")
        assert end == QDate(d.year(), 12, 31).toString("yyyy-MM-dd")

    def test_period_dates_term_defaults_to_three_months(self):
        tm = TimeManager()
        tm.current_period = "term"
        d = tm.current_date
        start, end = tm.period_dates()
        assert end == d.toString("yyyy-MM-dd")
        assert start == d.addMonths(-3).toString("yyyy-MM-dd")

    def test_period_dates_unit(self):
        tm = TimeManager()
        tm.unit_periods = [{"id": 3, "start_date": "2026-09-01", "end_date": "2026-10-09"}]
        tm.current_period = "unit_3"
        assert tm.period_dates() == ("2026-09-01", "2026-10-09")

    def test_period_dates_unknown_unit_falls_back_to_today(self):
        tm = TimeManager()
        tm.current_period = "unit_99"
        today = QDate.currentDate().toString("yyyy-MM-dd")
        assert tm.period_dates() == (today, today)

    def test_select_period_day_again_goes_today(self):
        tm = TimeManager()
        assert tm.select_period("day") is True
        assert tm.current_period == "day"

    def test_select_period_changes(self):
        tm = TimeManager()
        assert tm.select_period("week") is False
        assert tm.current_period == "week"

    def test_set_term(self):
        tm = TimeManager()
        tm.set_term(7, "T1 2027")
        assert tm.term_id == 7
        assert tm.term_label == "T1 2027"
