"""Sensor platform for the Sourdough Monitor integration."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import homeassistant.util.dt as dt_util
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfMass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_UNIT_SYSTEM,
    DOMAIN,
    SENSOR_DAY,
    SENSOR_DISCARD_AMOUNT,
    SENSOR_FEEDING_COUNT,
    SENSOR_FLOUR_TO_ADD,
    SENSOR_HYDRATION,
    SENSOR_INSTRUCTIONS,
    SENSOR_LAST_FED,
    SENSOR_NEXT_FEEDING,
    SENSOR_PHASE,
    SENSOR_STARTER_WEIGHT,
    SENSOR_TOTAL_WEIGHT,
    SENSOR_VESSEL_TARE,
    SENSOR_WATER_TO_ADD,
    UNIT_IMPERIAL,
    UNIT_METRIC,
)
from .coordinator import SourdoughCoordinator
from .units import format_flour_volume, format_water_volume, format_weight

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sourdough Monitor sensors."""
    coordinator: SourdoughCoordinator = hass.data[DOMAIN][entry.entry_id]
    unit_system = entry.data.get(CONF_UNIT_SYSTEM, UNIT_METRIC)

    entities = [
        SourdoughDaySensor(coordinator, entry, unit_system),
        SourdoughPhaseSensor(coordinator, entry, unit_system),
        SourdoughNextFeedingSensor(coordinator, entry, unit_system),
        SourdoughLastFedSensor(coordinator, entry, unit_system),
        SourdoughWeightSensor(
            coordinator, entry, unit_system,
            key=SENSOR_STARTER_WEIGHT,
            name="Starter Weight",
            data_key="starter_weight_g",
            icon="mdi:scale",
        ),
        SourdoughWeightSensor(
            coordinator, entry, unit_system,
            key=SENSOR_TOTAL_WEIGHT,
            name="Total Weight (with vessel)",
            data_key="total_weight_g",
            icon="mdi:scale-balance",
        ),
        SourdoughWeightSensor(
            coordinator, entry, unit_system,
            key=SENSOR_VESSEL_TARE,
            name="Vessel Tare Weight",
            data_key="vessel_tare_g",
            icon="mdi:bowl-outline",
        ),
        SourdoughWeightSensor(
            coordinator, entry, unit_system,
            key=SENSOR_FLOUR_TO_ADD,
            name="Flour to Add",
            data_key="flour_g",
            icon="mdi:shaker-outline",
            extra_fn=lambda g: {"volume_hint": format_flour_volume(g)},
        ),
        SourdoughWeightSensor(
            coordinator, entry, unit_system,
            key=SENSOR_WATER_TO_ADD,
            name="Water to Add",
            data_key="water_g",
            icon="mdi:water-outline",
            extra_fn=lambda g: {"volume_hint": format_water_volume(g)},
        ),
        SourdoughWeightSensor(
            coordinator, entry, unit_system,
            key=SENSOR_DISCARD_AMOUNT,
            name="Discard Amount",
            data_key="discard_amount_g",
            icon="mdi:trash-can-outline",
            extra_fn=lambda g: {"discard_required": g > 0},
        ),
        SourdoughHydrationSensor(coordinator, entry, unit_system),
        SourdoughFeedingCountSensor(coordinator, entry, unit_system),
        SourdoughInstructionsSensor(coordinator, entry, unit_system),
    ]

    async_add_entities(entities)


def _device_info(entry: ConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Sourdough Monitor",
        manufacturer="Community",
        model="Sourdough Starter Tracker",
        sw_version="1.0.0",
    )


class SourdoughBaseSensor(CoordinatorEntity[SourdoughCoordinator], SensorEntity):
    """Base class for all Sourdough sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SourdoughCoordinator,
        entry: ConfigEntry,
        unit_system: str,
        key: str,
        name: str,
        icon: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._unit_system = unit_system
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_icon = icon
        self._attr_device_info = _device_info(entry)

    @property
    def _data(self) -> dict[str, Any]:
        return self.coordinator.data or {}


class SourdoughDaySensor(SourdoughBaseSensor):
    """Current recipe day."""

    def __init__(self, coordinator, entry, unit_system):
        super().__init__(coordinator, entry, unit_system, SENSOR_DAY, "Current Day", "mdi:calendar-today")
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = "day"

    @property
    def native_value(self):
        return self._data.get("current_day")

    @property
    def extra_state_attributes(self):
        data = self._data
        return {
            "phase": data.get("phase"),
            "interval_hours": data.get("interval_hours"),
            "should_discard": data.get("should_discard"),
            "is_overdue": data.get("is_overdue"),
            "start_datetime": data.get("start_datetime"),
        }


class SourdoughPhaseSensor(SourdoughBaseSensor):
    """Current recipe phase."""

    def __init__(self, coordinator, entry, unit_system):
        super().__init__(coordinator, entry, unit_system, SENSOR_PHASE, "Phase", "mdi:progress-clock")

    @property
    def native_value(self):
        return self._data.get("phase")

    @property
    def extra_state_attributes(self):
        data = self._data
        return {
            "current_day": data.get("current_day"),
            "interval_hours": data.get("interval_hours"),
            "should_discard": data.get("should_discard"),
            "is_overdue": data.get("is_overdue"),
            "overdue_minutes": data.get("overdue_minutes"),
        }


class SourdoughNextFeedingSensor(SourdoughBaseSensor):
    """Timestamp of the next feeding due."""

    def __init__(self, coordinator, entry, unit_system):
        super().__init__(coordinator, entry, unit_system, SENSOR_NEXT_FEEDING, "Next Feeding Due", "mdi:alarm")
        self._attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> datetime | None:
        raw = self._data.get("next_feeding_dt")
        if raw:
            return dt_util.parse_datetime(raw)
        return None

    @property
    def extra_state_attributes(self):
        data = self._data
        return {
            "is_overdue": data.get("is_overdue"),
            "overdue_minutes": data.get("overdue_minutes"),
            "interval_hours": data.get("interval_hours"),
        }


class SourdoughLastFedSensor(SourdoughBaseSensor):
    """Timestamp of the last feeding."""

    def __init__(self, coordinator, entry, unit_system):
        super().__init__(coordinator, entry, unit_system, SENSOR_LAST_FED, "Last Fed", "mdi:clock-check-outline")
        self._attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> datetime | None:
        raw = self._data.get("last_feeding_dt")
        if raw:
            return dt_util.parse_datetime(raw)
        return None

    @property
    def extra_state_attributes(self):
        data = self._data
        return {"feeding_count": data.get("feeding_count")}


class SourdoughWeightSensor(SourdoughBaseSensor):
    """Generic weight sensor that converts to the user's unit preference."""

    def __init__(
        self,
        coordinator,
        entry,
        unit_system,
        key,
        name,
        data_key,
        icon="mdi:scale",
        extra_fn=None,
    ):
        super().__init__(coordinator, entry, unit_system, key, name, icon)
        self._data_key = data_key
        self._extra_fn = extra_fn
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_device_class = SensorDeviceClass.WEIGHT
        if unit_system == UNIT_IMPERIAL:
            self._attr_native_unit_of_measurement = "oz"
        else:
            self._attr_native_unit_of_measurement = UnitOfMass.GRAMS

    @property
    def native_value(self) -> float | None:
        grams = self._data.get(self._data_key)
        if grams is None:
            return None
        if self._unit_system == UNIT_IMPERIAL:
            from .units import grams_to_oz
            return grams_to_oz(grams)
        return round(grams, 1)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        grams = self._data.get(self._data_key)
        if grams is None:
            return {}
        attrs: dict[str, Any] = {"grams": round(grams, 1)}
        if self._unit_system == UNIT_METRIC:
            from .units import grams_to_oz
            attrs["oz"] = grams_to_oz(grams)
        else:
            attrs["grams"] = round(grams, 1)
        if self._extra_fn:
            attrs.update(self._extra_fn(grams))
        return attrs


class SourdoughHydrationSensor(SourdoughBaseSensor):
    """Hydration percentage (water / flour * 100)."""

    def __init__(self, coordinator, entry, unit_system):
        super().__init__(coordinator, entry, unit_system, SENSOR_HYDRATION, "Hydration", "mdi:water-percent")
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = "%"

    @property
    def native_value(self) -> float | None:
        return self._data.get("hydration_pct")

    @property
    def extra_state_attributes(self):
        data = self._data
        return {
            "flour_g": data.get("flour_g"),
            "water_g": data.get("water_g"),
        }


class SourdoughFeedingCountSensor(SourdoughBaseSensor):
    """Total number of feedings recorded."""

    def __init__(self, coordinator, entry, unit_system):
        super().__init__(coordinator, entry, unit_system, SENSOR_FEEDING_COUNT, "Total Feedings", "mdi:counter")
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self) -> int | None:
        return self._data.get("feeding_count")


class SourdoughInstructionsSensor(SourdoughBaseSensor):
    """Current instructions text sensor."""

    def __init__(self, coordinator, entry, unit_system):
        super().__init__(coordinator, entry, unit_system, SENSOR_INSTRUCTIONS, "Instructions", "mdi:text-box-outline")

    @property
    def native_value(self) -> str | None:
        instructions = self._data.get("instructions", "")
        # HA state is limited to 255 chars; full text in attributes
        if instructions and len(instructions) > 255:
            return instructions[:252] + "..."
        return instructions

    @property
    def extra_state_attributes(self):
        data = self._data
        return {
            "full_instructions": data.get("instructions"),
            "should_discard": data.get("should_discard"),
            "discard_amount_g": data.get("discard_amount_g"),
            "flour_to_add_g": data.get("flour_g"),
            "water_to_add_g": data.get("water_g"),
        }
