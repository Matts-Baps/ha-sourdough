"""Button entities for the Sourdough Monitor integration.

Provides one-tap actions visible on the device card in the HA UI.
"""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SourdoughCoordinator
from .sensor import _device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sourdough Monitor button entities."""
    coordinator: SourdoughCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([
        SourdoughRecordFeedingButton(coordinator, entry),
        SourdoughResetButton(coordinator, entry),
    ])


class SourdoughRecordFeedingButton(
    CoordinatorEntity[SourdoughCoordinator], ButtonEntity
):
    """Record a feeding using the current configured amounts.

    On Day 3 and beyond, the configured discard amount is applied
    automatically before recording the feeding.
    """

    _attr_has_entity_name = True
    _attr_name = "Record Feeding"
    _attr_icon = "mdi:bowl-mix-outline"

    def __init__(self, coordinator: SourdoughCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_record_feeding"
        self._attr_device_info = _device_info(entry)

    async def async_press(self) -> None:
        data = self.coordinator.data or {}
        discarded_g = data.get("discard_amount_g", 0.0) if data.get("should_discard") else 0.0
        await self.coordinator.async_record_feeding(discarded_g=discarded_g)


class SourdoughResetButton(
    CoordinatorEntity[SourdoughCoordinator], ButtonEntity
):
    """Reset the sourdough process back to Day 1."""

    _attr_has_entity_name = True
    _attr_name = "Reset Process"
    _attr_icon = "mdi:restart"

    def __init__(self, coordinator: SourdoughCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_reset"
        self._attr_device_info = _device_info(entry)

    async def async_press(self) -> None:
        await self.coordinator.async_reset()
