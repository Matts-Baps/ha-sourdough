"""Tests for the Sourdough Monitor config and options flows."""

import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sourdough.const import (
    CONF_DISCARD_RATIO,
    CONF_FLOUR_AMOUNT,
    CONF_UNIT_SYSTEM,
    CONF_VESSEL_TARE,
    CONF_WATER_AMOUNT,
    DOMAIN,
    UNIT_IMPERIAL,
    UNIT_METRIC,
)


AMOUNTS_METRIC = {
    CONF_FLOUR_AMOUNT: 60.0,
    CONF_WATER_AMOUNT: 60.0,
    CONF_VESSEL_TARE: 200.0,
    CONF_DISCARD_RATIO: 0.5,
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests in this module."""
    return


async def test_full_metric_flow(hass):
    """Happy path: set up the integration using metric units."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_UNIT_SYSTEM: UNIT_METRIC}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "amounts"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], AMOUNTS_METRIC
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_UNIT_SYSTEM] == UNIT_METRIC
    assert result["data"][CONF_FLOUR_AMOUNT] == pytest.approx(60.0)
    assert result["data"][CONF_WATER_AMOUNT] == pytest.approx(60.0)
    assert result["data"][CONF_VESSEL_TARE] == pytest.approx(200.0)


async def test_full_imperial_flow(hass):
    """Happy path: set up the integration using imperial units (oz converted to g on save)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_UNIT_SYSTEM: UNIT_IMPERIAL}
    )
    assert result["step_id"] == "amounts"

    # User enters 2.1 oz flour, 2.1 oz water, 7 oz vessel — expect conversion to grams
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_FLOUR_AMOUNT: 2.1,
            CONF_WATER_AMOUNT: 2.1,
            CONF_VESSEL_TARE: 7.0,
            CONF_DISCARD_RATIO: 0.5,
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    from custom_components.sourdough.const import GRAMS_PER_OZ
    assert result["data"][CONF_FLOUR_AMOUNT] == pytest.approx(2.1 * GRAMS_PER_OZ, rel=1e-3)
    assert result["data"][CONF_VESSEL_TARE] == pytest.approx(7.0 * GRAMS_PER_OZ, rel=1e-3)


async def test_invalid_flour_amount_shows_error(hass):
    """Zero flour should produce a validation error, not create an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_UNIT_SYSTEM: UNIT_METRIC}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**AMOUNTS_METRIC, CONF_FLOUR_AMOUNT: 0.0},
    )
    assert result["type"] == FlowResultType.FORM
    assert "flour_g" in result["errors"]


async def test_negative_vessel_tare_shows_error(hass):
    """Negative vessel tare should produce a validation error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_UNIT_SYSTEM: UNIT_METRIC}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**AMOUNTS_METRIC, CONF_VESSEL_TARE: -10.0},
    )
    assert result["type"] == FlowResultType.FORM
    assert "vessel_tare_g" in result["errors"]


async def test_options_flow_updates_amounts(hass):
    """Options flow should update amounts and store them in entry.options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_UNIT_SYSTEM: UNIT_METRIC,
            CONF_FLOUR_AMOUNT: 60.0,
            CONF_WATER_AMOUNT: 60.0,
            CONF_VESSEL_TARE: 0.0,
            CONF_DISCARD_RATIO: 0.5,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_FLOUR_AMOUNT: 80.0,
            CONF_WATER_AMOUNT: 70.0,
            CONF_VESSEL_TARE: 250.0,
            CONF_DISCARD_RATIO: 0.4,
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_FLOUR_AMOUNT] == pytest.approx(80.0)
    assert entry.options[CONF_DISCARD_RATIO] == pytest.approx(0.4)
