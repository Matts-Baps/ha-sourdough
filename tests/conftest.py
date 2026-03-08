"""Global test fixtures for the Sourdough Monitor integration."""

from unittest.mock import MagicMock

import pytest

from custom_components.sourdough.const import (
    CONF_DISCARD_RATIO,
    CONF_FLOUR_AMOUNT,
    CONF_UNIT_SYSTEM,
    CONF_VESSEL_TARE,
    CONF_WATER_AMOUNT,
    DEFAULT_DISCARD_RATIO,
    DEFAULT_FLOUR_GRAMS,
    DEFAULT_VESSEL_TARE_GRAMS,
    DEFAULT_WATER_GRAMS,
    UNIT_METRIC,
)
from custom_components.sourdough.coordinator import SourdoughCoordinator


DEFAULT_CONFIG = {
    CONF_UNIT_SYSTEM: UNIT_METRIC,
    CONF_FLOUR_AMOUNT: DEFAULT_FLOUR_GRAMS,
    CONF_WATER_AMOUNT: DEFAULT_WATER_GRAMS,
    CONF_VESSEL_TARE: DEFAULT_VESSEL_TARE_GRAMS,
    CONF_DISCARD_RATIO: DEFAULT_DISCARD_RATIO,
}


def make_coordinator(stored_data: dict, config_data: dict | None = None) -> SourdoughCoordinator:
    """Create a SourdoughCoordinator with mocked HA dependencies for unit testing."""
    hass = MagicMock()
    entry = MagicMock()
    entry.data = config_data or DEFAULT_CONFIG
    entry.options = {}
    entry.entry_id = "test_entry"
    coord = SourdoughCoordinator(hass, entry)
    coord._stored = stored_data
    return coord
