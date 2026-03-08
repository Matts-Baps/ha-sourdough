"""Number entities for the Sourdough Monitor integration.

These allow users to set the current day and current weight directly
from the HA UI, which is useful when setting up mid-recipe.
"""

from __future__ import annotations

import logging

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_UNIT_SYSTEM, DOMAIN, UNIT_IMPERIAL
from .coordinator import SourdoughCoordinator
from .sensor import _device_info
from .units import grams_to_oz, oz_to_grams

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sourdough Monitor number entities."""
    coordinator: SourdoughCoordinator = hass.data[DOMAIN][entry.entry_id]
    unit_system = entry.data.get(CONF_UNIT_SYSTEM, "metric")

    async_add_entities([
        SourdoughCurrentDayNumber(coordinator, entry),
        SourdoughCurrentWeightNumber(coordinator, entry, unit_system),
    ])


class SourdoughCurrentDayNumber(
    CoordinatorEntity[SourdoughCoordinator], NumberEntity
):
    """Set the current recipe day.

    Writing a new value calls async_set_day() on the coordinator,
    which backdates the start datetime so the day counter matches.
    """

    _attr_has_entity_name = True
    _attr_name = "Current Day"
    _attr_icon = "mdi:calendar-edit"
    _attr_native_min_value = 1
    _attr_native_max_value = 30
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = "day"

    def __init__(self, coordinator: SourdoughCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_set_day"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data:
            return float(self.coordinator.data["current_day"])
        return None

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_day(int(value))


class SourdoughCurrentWeightNumber(
    CoordinatorEntity[SourdoughCoordinator], NumberEntity
):
    """Set the current weight of the starter (including vessel by default).

    Writing a new value calls async_set_weight() on the coordinator,
    storing it as a baseline so future estimates build from this point.
    The value is displayed and accepted in the user's configured unit system.
    """

    _attr_has_entity_name = True
    _attr_name = "Current Weight (with vessel)"
    _attr_icon = "mdi:scale"
    _attr_mode = NumberMode.BOX
    _attr_device_class = NumberDeviceClass.WEIGHT
    _attr_native_min_value = 0

    def __init__(
        self,
        coordinator: SourdoughCoordinator,
        entry: ConfigEntry,
        unit_system: str,
    ) -> None:
        super().__init__(coordinator)
        self._unit_system = unit_system
        self._attr_unique_id = f"{entry.entry_id}_set_weight"
        self._attr_device_info = _device_info(entry)

        if unit_system == UNIT_IMPERIAL:
            self._attr_native_unit_of_measurement = "oz"
            self._attr_native_max_value = 352.0  # ~10 kg
            self._attr_native_step = 0.1
        else:
            self._attr_native_unit_of_measurement = "g"
            self._attr_native_max_value = 10000.0
            self._attr_native_step = 1.0

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None
        total_g = self.coordinator.data.get("total_weight_g", 0.0)
        if self._unit_system == UNIT_IMPERIAL:
            return grams_to_oz(total_g)
        return round(total_g, 1)

    async def async_set_native_value(self, value: float) -> None:
        weight_g = oz_to_grams(value) if self._unit_system == UNIT_IMPERIAL else value
        await self.coordinator.async_set_weight(weight_g=weight_g, includes_vessel=True)
