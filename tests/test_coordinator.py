"""Tests for coordinator logic: phase detection, weight estimation, day calculation.

dt_util.now() requires HA's event loop (Frame helper). All tests that touch
_compute_state() or create timestamps patch it via unittest.mock so no HA
infrastructure is needed.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from custom_components.sourdough.const import CONF_VESSEL_TARE
from custom_components.sourdough.coordinator import (
    _build_instructions,
    _get_phase_for_day,
    _phase_label,
)
from .conftest import DEFAULT_CONFIG, make_coordinator

# Fixed "now" used across all tests that need a stable clock
_NOW = datetime(2026, 3, 8, 12, 0, 0, tzinfo=timezone.utc)

# Patch target for dt_util.now inside the coordinator module
_DT_NOW = "custom_components.sourdough.coordinator.dt_util.now"
# Patch target for dt_util.parse_datetime (returns timezone-aware datetimes)
_DT_PARSE = "custom_components.sourdough.coordinator.dt_util.parse_datetime"


def _ts(dt: datetime) -> str:
    """ISO format helper."""
    return dt.isoformat()


class TestPhaseForDay:
    @pytest.mark.parametrize("day,expected_hours,expected_discard", [
        (1, 24, False),
        (2, 24, False),
        (3, 24, True),
        (4, 24, True),
        (5, 24, True),
        (6, 12, True),
        (7, 12, True),
        (8, 12, True),
        (20, 12, True),
    ])
    def test_phase_schedule(self, day, expected_hours, expected_discard):
        hours, discard = _get_phase_for_day(day)
        assert hours == expected_hours
        assert discard == expected_discard


class TestPhaseLabel:
    @pytest.mark.parametrize("day,expected", [
        (1, "Initialization"),
        (2, "Initialization"),
        (3, "Establishment"),
        (5, "Establishment"),
        (6, "Activation"),
        (7, "Activation"),
        (8, "Maintenance"),
        (30, "Maintenance"),
    ])
    def test_labels(self, day, expected):
        assert _phase_label(day) == expected


class TestBuildInstructions:
    def test_day1_no_urgency(self):
        result = _build_instructions(1, False, 24, False, 0)
        assert "flour" in result.lower()
        assert "overdue" not in result.lower()

    def test_overdue_message_included(self):
        result = _build_instructions(3, True, 24, True, 90)
        assert "overdue" in result.lower()
        assert "1h 30m" in result

    def test_day3_mentions_discard(self):
        result = _build_instructions(3, True, 24, False, 0)
        assert "discard" in result.lower()

    def test_maintenance_mentions_active(self):
        result = _build_instructions(10, True, 12, False, 0)
        assert "active" in result.lower()


class TestWeightEstimation:
    """These tests call _estimate_starter_weight directly.

    That method only uses dt_util.parse_datetime (not dt_util.now), but we
    use plain datetime objects in test timestamps to avoid any HA dependency.
    """

    def _coord(self, stored=None):
        return make_coordinator(stored or {
            "start_datetime": _ts(_NOW),
            "feedings": [],
        })

    def test_no_feedings_no_baseline_returns_zero(self):
        coord = self._coord()
        assert coord._estimate_starter_weight([], 60, 60, 0.5) == 0.0

    def test_single_feeding_accumulates(self):
        coord = self._coord()
        feedings = [{"timestamp": _ts(_NOW), "flour_g": 60, "water_g": 60, "discarded_g": 0}]
        assert coord._estimate_starter_weight(feedings, 60, 60, 0.5) == pytest.approx(120.0)

    def test_discard_reduces_weight(self):
        coord = self._coord()
        feedings = [
            {"timestamp": _ts(_NOW), "flour_g": 60, "water_g": 60, "discarded_g": 0},
            {"timestamp": _ts(_NOW + timedelta(hours=24)), "flour_g": 60, "water_g": 60, "discarded_g": 60},
        ]
        # After feeding 1: 120g. Feeding 2: discard 60 → 60g, add 120 → 180g
        assert coord._estimate_starter_weight(feedings, 60, 60, 0.5) == pytest.approx(180.0)

    def test_weight_cannot_go_negative(self):
        coord = self._coord()
        feedings = [{"timestamp": _ts(_NOW), "flour_g": 10, "water_g": 10, "discarded_g": 9999}]
        assert coord._estimate_starter_weight(feedings, 60, 60, 0.5) >= 0.0

    def test_baseline_used_as_starting_weight(self):
        baseline_ts = _NOW - timedelta(hours=1)
        feeding_ts = _NOW
        stored = {
            "start_datetime": _ts(_NOW - timedelta(days=2)),
            "feedings": [],
            "weight_baseline": {"timestamp": _ts(baseline_ts), "weight_g": 200.0},
        }
        coord = make_coordinator(stored)
        feedings = [{"timestamp": _ts(feeding_ts), "flour_g": 60, "water_g": 60, "discarded_g": 0}]
        # baseline 200 + 60 flour + 60 water = 320
        assert coord._estimate_starter_weight(feedings, 60, 60, 0.5) == pytest.approx(320.0)

    def test_feedings_before_baseline_are_ignored(self):
        baseline_ts = _NOW
        old_feeding_ts = _NOW - timedelta(hours=2)
        stored = {
            "start_datetime": _ts(_NOW - timedelta(days=2)),
            "feedings": [],
            "weight_baseline": {"timestamp": _ts(baseline_ts), "weight_g": 200.0},
        }
        coord = make_coordinator(stored)
        feedings = [{"timestamp": _ts(old_feeding_ts), "flour_g": 60, "water_g": 60, "discarded_g": 0}]
        assert coord._estimate_starter_weight(feedings, 60, 60, 0.5) == pytest.approx(200.0)


class TestComputeState:
    """Tests for _compute_state.

    dt_util.now() is patched to _NOW so results are deterministic and
    no HA Frame helper is required.
    """

    def test_day1_on_fresh_start(self):
        stored = {"start_datetime": _ts(_NOW), "feedings": []}
        coord = make_coordinator(stored)
        with patch(_DT_NOW, return_value=_NOW):
            state = coord._compute_state()
        assert state["current_day"] == 1
        assert state["phase"] == "Initialization"
        assert state["should_discard"] is False
        assert state["starter_weight_g"] == 0.0

    def test_day3_requires_discard(self):
        start = _NOW - timedelta(days=2, hours=1)
        stored = {"start_datetime": _ts(start), "feedings": []}
        coord = make_coordinator(stored)
        with patch(_DT_NOW, return_value=_NOW):
            state = coord._compute_state()
        assert state["current_day"] == 3
        assert state["should_discard"] is True
        assert state["phase"] == "Establishment"

    def test_total_weight_includes_vessel_tare(self):
        stored = {
            "start_datetime": _ts(_NOW),
            "feedings": [
                {"timestamp": _ts(_NOW), "flour_g": 60, "water_g": 60, "discarded_g": 0}
            ],
        }
        config = {**DEFAULT_CONFIG, CONF_VESSEL_TARE: 200.0}
        coord = make_coordinator(stored, config)
        with patch(_DT_NOW, return_value=_NOW):
            state = coord._compute_state()
        # starter = 120g, vessel = 200g → total = 320g
        assert state["total_weight_g"] == pytest.approx(320.0)
        assert state["starter_weight_g"] == pytest.approx(120.0)

    def test_no_discard_on_days_1_and_2(self):
        for days_ago in [0, 1]:
            start = _NOW - timedelta(days=days_ago)
            stored = {"start_datetime": _ts(start), "feedings": []}
            coord = make_coordinator(stored)
            with patch(_DT_NOW, return_value=_NOW):
                state = coord._compute_state()
            assert state["discard_amount_g"] == 0.0

    def test_is_overdue_when_past_next_feeding(self):
        # Started 25h ago (day 1 → 24h interval), no feedings → overdue by ~1h
        start = _NOW - timedelta(hours=25)
        stored = {"start_datetime": _ts(start), "feedings": []}
        coord = make_coordinator(stored)
        with patch(_DT_NOW, return_value=_NOW):
            state = coord._compute_state()
        assert state["is_overdue"] is True
        assert state["overdue_minutes"] > 0

    def test_hydration_calculation(self):
        stored = {"start_datetime": _ts(_NOW), "feedings": []}
        # Default config: 60g flour, 60g water → 100% hydration
        coord = make_coordinator(stored)
        with patch(_DT_NOW, return_value=_NOW):
            state = coord._compute_state()
        assert state["hydration_pct"] == pytest.approx(100.0)
