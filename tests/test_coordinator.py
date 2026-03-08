"""Tests for coordinator logic: phase detection, weight estimation, day calculation."""

from datetime import timedelta

import pytest
import homeassistant.util.dt as dt_util

from custom_components.sourdough.const import CONF_VESSEL_TARE
from custom_components.sourdough.coordinator import (
    _build_instructions,
    _get_phase_for_day,
    _phase_label,
)
from .conftest import DEFAULT_CONFIG, make_coordinator


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
    def test_no_feedings_no_baseline_returns_zero(self):
        coord = make_coordinator({"start_datetime": dt_util.now().isoformat(), "feedings": []})
        assert coord._estimate_starter_weight([], 60, 60, 0.5) == 0.0

    def test_single_feeding_accumulates(self):
        coord = make_coordinator({"start_datetime": dt_util.now().isoformat(), "feedings": []})
        feedings = [{"timestamp": dt_util.now().isoformat(), "flour_g": 60, "water_g": 60, "discarded_g": 0}]
        assert coord._estimate_starter_weight(feedings, 60, 60, 0.5) == pytest.approx(120.0)

    def test_discard_reduces_weight(self):
        coord = make_coordinator({"start_datetime": dt_util.now().isoformat(), "feedings": []})
        feedings = [
            {"timestamp": dt_util.now().isoformat(), "flour_g": 60, "water_g": 60, "discarded_g": 0},
            {"timestamp": dt_util.now().isoformat(), "flour_g": 60, "water_g": 60, "discarded_g": 60},
        ]
        # After feeding 1: 120g. Feeding 2: discard 60 → 60, add 120 → 180g
        assert coord._estimate_starter_weight(feedings, 60, 60, 0.5) == pytest.approx(180.0)

    def test_weight_cannot_go_negative(self):
        coord = make_coordinator({"start_datetime": dt_util.now().isoformat(), "feedings": []})
        # Discard more than we have
        feedings = [{"timestamp": dt_util.now().isoformat(), "flour_g": 10, "water_g": 10, "discarded_g": 9999}]
        result = coord._estimate_starter_weight(feedings, 60, 60, 0.5)
        assert result >= 0.0

    def test_baseline_used_as_starting_weight(self):
        baseline_ts = dt_util.now() - timedelta(hours=1)
        feeding_ts = dt_util.now()
        stored = {
            "start_datetime": (dt_util.now() - timedelta(days=2)).isoformat(),
            "feedings": [],
            "weight_baseline": {
                "timestamp": baseline_ts.isoformat(),
                "weight_g": 200.0,
            },
        }
        coord = make_coordinator(stored)
        feedings = [{"timestamp": feeding_ts.isoformat(), "flour_g": 60, "water_g": 60, "discarded_g": 0}]
        # baseline 200 + 60 flour + 60 water = 320
        assert coord._estimate_starter_weight(feedings, 60, 60, 0.5) == pytest.approx(320.0)

    def test_feedings_before_baseline_are_ignored(self):
        baseline_ts = dt_util.now()
        old_feeding_ts = dt_util.now() - timedelta(hours=2)
        stored = {
            "start_datetime": (dt_util.now() - timedelta(days=2)).isoformat(),
            "feedings": [],
            "weight_baseline": {
                "timestamp": baseline_ts.isoformat(),
                "weight_g": 200.0,
            },
        }
        coord = make_coordinator(stored)
        # This feeding happened before the baseline — should not be replayed
        feedings = [{"timestamp": old_feeding_ts.isoformat(), "flour_g": 60, "water_g": 60, "discarded_g": 0}]
        assert coord._estimate_starter_weight(feedings, 60, 60, 0.5) == pytest.approx(200.0)


class TestComputeState:
    def test_day1_on_fresh_start(self):
        stored = {
            "start_datetime": dt_util.now().isoformat(),
            "feedings": [],
        }
        coord = make_coordinator(stored)
        state = coord._compute_state()
        assert state["current_day"] == 1
        assert state["phase"] == "Initialization"
        assert state["should_discard"] is False
        assert state["starter_weight_g"] == 0.0

    def test_day3_requires_discard(self):
        stored = {
            "start_datetime": (dt_util.now() - timedelta(days=2, hours=1)).isoformat(),
            "feedings": [],
        }
        coord = make_coordinator(stored)
        state = coord._compute_state()
        assert state["current_day"] == 3
        assert state["should_discard"] is True
        assert state["phase"] == "Establishment"

    def test_total_weight_includes_vessel_tare(self):
        stored = {
            "start_datetime": dt_util.now().isoformat(),
            "feedings": [
                {"timestamp": dt_util.now().isoformat(), "flour_g": 60, "water_g": 60, "discarded_g": 0}
            ],
            "weight_baseline": None,
        }
        config = {**DEFAULT_CONFIG, CONF_VESSEL_TARE: 200.0}
        coord = make_coordinator(stored, config)
        state = coord._compute_state()
        # starter = 120g, vessel = 200g → total = 320g
        assert state["total_weight_g"] == pytest.approx(320.0)
        assert state["starter_weight_g"] == pytest.approx(120.0)

    def test_no_discard_on_days_1_and_2(self):
        for days_ago in [0, 1]:
            stored = {
                "start_datetime": (dt_util.now() - timedelta(days=days_ago)).isoformat(),
                "feedings": [],
            }
            coord = make_coordinator(stored)
            state = coord._compute_state()
            assert state["discard_amount_g"] == 0.0

    def test_is_overdue_when_past_next_feeding(self):
        # Last fed 25 hours ago on a 24h schedule (day 1)
        last_fed = dt_util.now() - timedelta(hours=25)
        stored = {
            "start_datetime": (dt_util.now() - timedelta(hours=25)).isoformat(),
            "feedings": [
                {"timestamp": last_fed.isoformat(), "flour_g": 60, "water_g": 60, "discarded_g": 0}
            ],
        }
        coord = make_coordinator(stored)
        state = coord._compute_state()
        assert state["is_overdue"] is True
        assert state["overdue_minutes"] > 0

    def test_hydration_calculation(self):
        stored = {"start_datetime": dt_util.now().isoformat(), "feedings": []}
        # Default config: 60g flour, 60g water → 100% hydration
        coord = make_coordinator(stored)
        state = coord._compute_state()
        assert state["hydration_pct"] == pytest.approx(100.0)
