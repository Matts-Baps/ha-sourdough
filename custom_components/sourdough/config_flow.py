"""Config flow for the Sourdough Monitor integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    CONF_DISCARD_RATIO,
    CONF_FLOUR_AMOUNT,
    CONF_UNIT_SYSTEM,
    CONF_VESSEL_TARE,
    CONF_WATER_AMOUNT,
    DEFAULT_DISCARD_RATIO,
    DEFAULT_FLOUR_GRAMS,
    DEFAULT_VESSEL_TARE_GRAMS,
    DEFAULT_WATER_GRAMS,
    DOMAIN,
    GRAMS_PER_OZ,
    UNIT_IMPERIAL,
    UNIT_METRIC,
)

_LOGGER = logging.getLogger(__name__)


def _schema_for_units(unit_system: str, defaults: dict) -> vol.Schema:
    """Build a voluptuous schema using the correct unit labels."""
    if unit_system == UNIT_IMPERIAL:
        flour_default = round(defaults.get(CONF_FLOUR_AMOUNT, DEFAULT_FLOUR_GRAMS) / GRAMS_PER_OZ, 2)
        water_default = round(defaults.get(CONF_WATER_AMOUNT, DEFAULT_WATER_GRAMS) / GRAMS_PER_OZ, 2)
        vessel_default = round(defaults.get(CONF_VESSEL_TARE, DEFAULT_VESSEL_TARE_GRAMS) / GRAMS_PER_OZ, 2)
    else:
        flour_default = defaults.get(CONF_FLOUR_AMOUNT, DEFAULT_FLOUR_GRAMS)
        water_default = defaults.get(CONF_WATER_AMOUNT, DEFAULT_WATER_GRAMS)
        vessel_default = defaults.get(CONF_VESSEL_TARE, DEFAULT_VESSEL_TARE_GRAMS)

    return vol.Schema(
        {
            vol.Required(CONF_FLOUR_AMOUNT, default=flour_default): vol.Coerce(float),
            vol.Required(CONF_WATER_AMOUNT, default=water_default): vol.Coerce(float),
            vol.Required(CONF_VESSEL_TARE, default=vessel_default): vol.Coerce(float),
            vol.Required(CONF_DISCARD_RATIO, default=defaults.get(CONF_DISCARD_RATIO, DEFAULT_DISCARD_RATIO)): vol.All(
                vol.Coerce(float), vol.Range(min=0.1, max=0.9)
            ),
        }
    )


def _to_grams(value: float, unit_system: str) -> float:
    """Convert user input to grams."""
    if unit_system == UNIT_IMPERIAL:
        return value * GRAMS_PER_OZ
    return value


class SourdoughConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sourdough Monitor."""

    VERSION = 1

    def __init__(self) -> None:
        self._unit_system: str = UNIT_METRIC

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Step 1: choose unit system."""
        if user_input is not None:
            self._unit_system = user_input[CONF_UNIT_SYSTEM]
            return await self.async_step_amounts()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_UNIT_SYSTEM, default=UNIT_METRIC): vol.In(
                        {UNIT_METRIC: "Metric (grams)", UNIT_IMPERIAL: "Imperial (oz)"}
                    ),
                }
            ),
            description_placeholders={
                "info": "All values are stored in grams internally. Imperial values are converted automatically."
            },
        )

    async def async_step_amounts(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Step 2: set feeding amounts and vessel tare."""
        errors: dict[str, str] = {}

        if user_input is not None:
            flour_g = _to_grams(user_input[CONF_FLOUR_AMOUNT], self._unit_system)
            water_g = _to_grams(user_input[CONF_WATER_AMOUNT], self._unit_system)
            vessel_g = _to_grams(user_input[CONF_VESSEL_TARE], self._unit_system)
            discard_ratio = user_input[CONF_DISCARD_RATIO]

            if flour_g <= 0:
                errors[CONF_FLOUR_AMOUNT] = "flour_must_be_positive"
            if water_g <= 0:
                errors[CONF_WATER_AMOUNT] = "water_must_be_positive"
            if vessel_g < 0:
                errors[CONF_VESSEL_TARE] = "vessel_must_be_non_negative"

            if not errors:
                return self.async_create_entry(
                    title="Sourdough Starter",
                    data={
                        CONF_UNIT_SYSTEM: self._unit_system,
                        CONF_FLOUR_AMOUNT: round(flour_g, 2),
                        CONF_WATER_AMOUNT: round(water_g, 2),
                        CONF_VESSEL_TARE: round(vessel_g, 2),
                        CONF_DISCARD_RATIO: discard_ratio,
                    },
                )

        schema = _schema_for_units(self._unit_system, {})
        return self.async_show_form(
            step_id="amounts",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "unit": "oz" if self._unit_system == UNIT_IMPERIAL else "g",
                "recipe_flour": "2.1 oz" if self._unit_system == UNIT_IMPERIAL else "60 g",
                "recipe_water": "2.1 oz" if self._unit_system == UNIT_IMPERIAL else "60 g",
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SourdoughOptionsFlow:
        """Return the options flow handler."""
        return SourdoughOptionsFlow(config_entry)


class SourdoughOptionsFlow(config_entries.OptionsFlow):
    """Handle options for the Sourdough Monitor integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        current = dict(self._config_entry.data)
        current.update(self._config_entry.options or {})
        unit_system = current.get(CONF_UNIT_SYSTEM, UNIT_METRIC)

        if user_input is not None:
            flour_g = _to_grams(user_input[CONF_FLOUR_AMOUNT], unit_system)
            water_g = _to_grams(user_input[CONF_WATER_AMOUNT], unit_system)
            vessel_g = _to_grams(user_input[CONF_VESSEL_TARE], unit_system)
            discard_ratio = user_input[CONF_DISCARD_RATIO]

            if flour_g <= 0:
                errors[CONF_FLOUR_AMOUNT] = "flour_must_be_positive"
            if water_g <= 0:
                errors[CONF_WATER_AMOUNT] = "water_must_be_positive"
            if vessel_g < 0:
                errors[CONF_VESSEL_TARE] = "vessel_must_be_non_negative"

            if not errors:
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_FLOUR_AMOUNT: round(flour_g, 2),
                        CONF_WATER_AMOUNT: round(water_g, 2),
                        CONF_VESSEL_TARE: round(vessel_g, 2),
                        CONF_DISCARD_RATIO: discard_ratio,
                    },
                )

        schema = _schema_for_units(unit_system, current)
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )
