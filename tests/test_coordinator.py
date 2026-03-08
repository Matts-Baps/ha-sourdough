"""Tests for coordinator logic: phase detection, weight estimation, day calculation.

Weight estimation tests call the module-level pure function directly — no HA
infrastructure needed. _compute_state tests use the hass fixture (which sets
up the Frame helper) with dt_util.now patched to a fixed datetime.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sourdough.const import CONF_VESSEL_TARE, DOMAIN
from custom_components.sourdough.coordinator import (
    SourdoughCoordinator,
    _build_instructions,
    _get_phase_for_day,
    _phase_label,
    estimate_starter_weight,
)
from .conftest import DEFAULT_CONFIG

# Fixed "now" used across all tests that need a stable clock
_NOW = datetime(2026, 3, 8, 12, 0, 0, tzinfo=timezone.utc)
_DT_NOW = "custom_components.sourdough.coordinator.dt_util.now"


def _ts(dt: datetime) -> str:
    return dt.isoformat()


# ---------------------------------------------------------------------------
# Pure function tests — no HA required
# ---------------------------------------------------------------------------

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


class TestEstimateStarterWeight:
    """Tests for the module-level estimate_starter_weight pure function."""

    def test_no_feedings_no_baseline_returns_zero(self):
        assert estimate_starter_weight([], 60, 60) == 0.0

    def test_single_feeding_accumulates(self):
        feedings = [{"timestamp": _ts(_NOW), "flour_g": 60, "water_g": 60, "discarded_g": 0}]
        assert estimate_starter_weight(feedings, 60, 60) == pytest.approx(120.0)

    def test_discard_reduces_weight(self):
        feedings = [
            {"timestamp": _ts(_NOW), "flour_g": 60, "water_g": 60, "discarded_g": 0},
            {"timestamp": _ts(_NOW + timedelta(hours=24)), "flour_g": 60, "water_g": 60, "discarded_g": 60},
        ]
        # After feeding 1: 120g. Feeding 2: discard 60 → 60g, add 120 → 180g
        assert estimate_starter_weight(feedings, 60, 60) == pytest.approx(180.0)

    def test_weight_cannot_go_negative(self):
        feedings = [{"timestamp": _ts(_NOW), "flour_g": 10, "water_g": 10, "discarded_g": 9999}]
        assert estimate_starter_weight(feedings, 60, 60) >= 0.0

    def test_baseline_used_as_starting_weight(self):
        baseline = {"timestamp": _ts(_NOW - timedelta(hours=1)), "weight_g": 200.0}
        feedings = [{"timestamp": _ts(_NOW), "flour_g": 60, "water_g": 60, "discarded_g": 0}]
        # baseline 200 + 60 flour + 60 water = 320
        assert estimate_starter_weight(feedings, 60, 60, baseline) == pytest.approx(320.0)

    def test_feedings_before_baseline_are_ignored(self):
        baseline = {"timestamp": _ts(_NOW), "weight_g": 200.0}
        old_feeding = {"timestamp": _ts(_NOW - timedelta(hours=2)), "flour_g": 60, "water_g": 60, "discarded_g": 0}
        assert estimate_starter_weight([old_feeding], 60, 60, baseline) == pytest.approx(200.0)


# ---------------------------------------------------------------------------
# _compute_state tests — require hass fixture for the Frame helper
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    return


def _make_coord(hass, config=None, stored=None):
    """Create a coordinator with real hass but mocked Store."""
    entry = MockConfigEntry(domain=DOMAIN, data=config or DEFAULT_CONFIG)
    entry.add_to_hass(hass)
    coord = SourdoughCoordinator(hass, entry)
    coord._stored = stored or {"start_datetime": _ts(_NOW), "feedings": []}
    return coord


class TestComputeState:
    async def test_day1_on_fresh_start(self, hass):
        coord = _make_coord(hass)
        with patch(_DT_NOW, return_value=_NOW):
            state = coord._compute_state()
        assert state["current_day"] == 1
        assert state["phase"] == "Initialization"
        assert state["should_discard"] is False
        assert state["starter_weight_g"] == 0.0

    async def test_day3_requires_discard(self, hass):
        stored = {"start_datetime": _ts(_NOW - timedelta(days=2, hours=1)), "feedings": []}
        coord = _make_coord(hass, stored=stored)
        with patch(_DT_NOW, return_value=_NOW):
            state = coord._compute_state()
        assert state["current_day"] == 3
        assert state["should_discard"] is True
        assert state["phase"] == "Establishment"

    async def test_total_weight_includes_vessel_tare(self, hass):
        stored = {
            "start_datetime": _ts(_NOW),
            "feedings": [
                {"timestamp": _ts(_NOW), "flour_g": 60, "water_g": 60, "discarded_g": 0}
            ],
        }
        config = {**DEFAULT_CONFIG, CONF_VESSEL_TARE: 200.0}
        coord = _make_coord(hass, config=config, stored=stored)
        with patch(_DT_NOW, return_value=_NOW):
            state = coord._compute_state()
        assert state["total_weight_g"] == pytest.approx(320.0)
        assert state["starter_weight_g"] == pytest.approx(120.0)

    async def test_no_discard_on_days_1_and_2(self, hass):
        for days_ago in [0, 1]:
            stored = {"start_datetime": _ts(_NOW - timedelta(days=days_ago)), "feedings": []}
            coord = _make_coord(hass, stored=stored)
            with patch(_DT_NOW, return_value=_NOW):
                state = coord._compute_state()
            assert state["discard_amount_g"] == 0.0

    async def test_is_overdue_when_past_next_feeding(self, hass):
        # Started 25h ago (day 1, 24h interval), no feedings → overdue
        stored = {"start_datetime": _ts(_NOW - timedelta(hours=25)), "feedings": []}
        coord = _make_coord(hass, stored=stored)
        with patch(_DT_NOW, return_value=_NOW):
            state = coord._compute_state()
        assert state["is_overdue"] is True
        assert state["overdue_minutes"] > 0

    async def test_hydration_calculation(self, hass):
        coord = _make_coord(hass)
        with patch(_DT_NOW, return_value=_NOW):
            state = coord._compute_state()
        # Default config: 60g flour, 60g water → 100%
        assert state["hydration_pct"] == pytest.approx(100.0)
