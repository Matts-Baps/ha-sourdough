"""The Sourdough Monitor integration."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_UNIT_SYSTEM,
    DOMAIN,
    GRAMS_PER_OZ,
    SERVICE_RECORD_FEEDING,
    SERVICE_RESET,
    SERVICE_SET_DAY,
    SERVICE_SET_WEIGHT,
    UNIT_IMPERIAL,
)
from .coordinator import SourdoughCoordinator

_LOGGER = logging.getLogger(__name__)

_PLATFORMS = [Platform.SENSOR, Platform.NUMBER, Platform.BUTTON]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sourdough Monitor from a config entry."""
    coordinator = SourdoughCoordinator(hass, entry)
    await coordinator.async_load()
    await coordinator.async_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    _register_services(hass, entry, coordinator)

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        # Remove services if no more entries
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_RECORD_FEEDING)
            hass.services.async_remove(DOMAIN, SERVICE_RESET)
            hass.services.async_remove(DOMAIN, SERVICE_SET_DAY)
            hass.services.async_remove(DOMAIN, SERVICE_SET_WEIGHT)
    return unload_ok


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    coordinator: SourdoughCoordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_refresh()


def _unit_system(entry: ConfigEntry) -> str:
    cfg = dict(entry.data)
    cfg.update(entry.options or {})
    return cfg.get(CONF_UNIT_SYSTEM, "metric")


def _to_grams(value: float, unit_system: str) -> float:
    """Convert user-supplied value to grams."""
    if unit_system == UNIT_IMPERIAL:
        return value * GRAMS_PER_OZ
    return value


def _register_services(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: SourdoughCoordinator,
) -> None:
    """Register integration services."""

    # Service: record_feeding
    # Accepts optional flour, water, and discarded amounts.
    # Amounts are in the user's configured unit system (g or oz).
    record_schema = vol.Schema(
        {
            vol.Optional("entry_id"): cv.string,
            vol.Optional("flour"): vol.Coerce(float),
            vol.Optional("water"): vol.Coerce(float),
            vol.Optional("discarded"): vol.Coerce(float),
            vol.Optional("timestamp"): cv.datetime,
        }
    )

    async def handle_record_feeding(call: ServiceCall) -> None:
        target_entry_id = call.data.get("entry_id", entry.entry_id)
        target_coordinator: SourdoughCoordinator = hass.data[DOMAIN].get(target_entry_id)
        if target_coordinator is None:
            _LOGGER.error("No sourdough entry found with id: %s", target_entry_id)
            return

        target_entry = hass.config_entries.async_get_entry(target_entry_id)
        us = _unit_system(target_entry) if target_entry else "metric"

        flour_raw = call.data.get("flour")
        water_raw = call.data.get("water")
        discarded_raw = call.data.get("discarded")
        timestamp = call.data.get("timestamp")

        flour_g = _to_grams(flour_raw, us) if flour_raw is not None else None
        water_g = _to_grams(water_raw, us) if water_raw is not None else None
        discarded_g = _to_grams(discarded_raw, us) if discarded_raw is not None else None

        await target_coordinator.async_record_feeding(
            flour_g=flour_g,
            water_g=water_g,
            discarded_g=discarded_g,
            timestamp=timestamp,
        )

    # Service: reset_process
    reset_schema = vol.Schema(
        {
            vol.Optional("entry_id"): cv.string,
        }
    )

    async def handle_reset(call: ServiceCall) -> None:
        target_entry_id = call.data.get("entry_id", entry.entry_id)
        target_coordinator: SourdoughCoordinator = hass.data[DOMAIN].get(target_entry_id)
        if target_coordinator is None:
            _LOGGER.error("No sourdough entry found with id: %s", target_entry_id)
            return
        await target_coordinator.async_reset()

    # Service: set_day
    set_day_schema = vol.Schema(
        {
            vol.Optional("entry_id"): cv.string,
            vol.Required("day"): vol.All(vol.Coerce(int), vol.Range(min=1)),
        }
    )

    async def handle_set_day(call: ServiceCall) -> None:
        target_entry_id = call.data.get("entry_id", entry.entry_id)
        target_coordinator: SourdoughCoordinator = hass.data[DOMAIN].get(target_entry_id)
        if target_coordinator is None:
            _LOGGER.error("No sourdough entry found with id: %s", target_entry_id)
            return
        await target_coordinator.async_set_day(call.data["day"])

    # Only register services once (they work across all entries via entry_id)
    if not hass.services.has_service(DOMAIN, SERVICE_RECORD_FEEDING):
        hass.services.async_register(
            DOMAIN,
            SERVICE_RECORD_FEEDING,
            handle_record_feeding,
            schema=record_schema,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_RESET):
        hass.services.async_register(
            DOMAIN,
            SERVICE_RESET,
            handle_reset,
            schema=reset_schema,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_SET_DAY):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_DAY,
            handle_set_day,
            schema=set_day_schema,
        )

    # Service: set_weight
    set_weight_schema = vol.Schema(
        {
            vol.Optional("entry_id"): cv.string,
            vol.Required("weight"): vol.All(vol.Coerce(float), vol.Range(min=0)),
            vol.Optional("includes_vessel", default=True): cv.boolean,
        }
    )

    async def handle_set_weight(call: ServiceCall) -> None:
        target_entry_id = call.data.get("entry_id", entry.entry_id)
        target_coordinator: SourdoughCoordinator = hass.data[DOMAIN].get(target_entry_id)
        if target_coordinator is None:
            _LOGGER.error("No sourdough entry found with id: %s", target_entry_id)
            return

        target_entry = hass.config_entries.async_get_entry(target_entry_id)
        us = _unit_system(target_entry) if target_entry else "metric"
        weight_g = _to_grams(call.data["weight"], us)
        await target_coordinator.async_set_weight(
            weight_g=weight_g,
            includes_vessel=call.data["includes_vessel"],
        )

    if not hass.services.has_service(DOMAIN, SERVICE_SET_WEIGHT):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_WEIGHT,
            handle_set_weight,
            schema=set_weight_schema,
        )
