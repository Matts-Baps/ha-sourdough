"""Data update coordinator for the Sourdough Monitor integration."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import homeassistant.util.dt as dt_util
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DEFAULT_DISCARD_RATIO,
    DEFAULT_FLOUR_GRAMS,
    DEFAULT_VESSEL_TARE_GRAMS,
    DEFAULT_WATER_GRAMS,
    DOMAIN,
    RECIPE_PHASES,
    STORAGE_KEY,
    STORAGE_VERSION,
    CONF_FLOUR_AMOUNT,
    CONF_WATER_AMOUNT,
    CONF_DISCARD_RATIO,
    CONF_VESSEL_TARE,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=1)


def _get_phase_for_day(day: int) -> tuple[int, bool]:
    """Return (interval_hours, should_discard) for the given recipe day."""
    for min_day, max_day, interval_hours, discard in RECIPE_PHASES:
        if min_day <= day <= max_day:
            return interval_hours, discard
    # Fallback: maintenance
    return 12, True


def _phase_label(day: int) -> str:
    """Return a human-readable phase label."""
    if day <= 2:
        return "Initialization"
    if day <= 5:
        return "Establishment"
    if day <= 7:
        return "Activation"
    return "Maintenance"


def _build_instructions(day: int, should_discard: bool, interval_hours: int, is_overdue: bool, overdue_minutes: float) -> str:
    """Build a plain-text instruction string for the current state."""
    if is_overdue:
        overdue_h = int(overdue_minutes // 60)
        overdue_m = int(overdue_minutes % 60)
        overdue_str = f"{overdue_h}h {overdue_m}m" if overdue_h else f"{overdue_m}m"
        urgency = f"Feeding is overdue by {overdue_str}! "
    else:
        urgency = ""

    if day == 1:
        action = "Mix flour and water in your jar. Cover with cloth and leave for 24 hours."
    elif day == 2:
        action = "Add flour and water to the existing starter. Cover and leave for 24 hours."
    elif day <= 5:
        action = "Discard half the starter, then add flour and water. Cover and leave for 24 hours."
    elif day <= 7:
        action = "Discard half the starter, then add flour and water. Feed every 12 hours."
    else:
        action = (
            "Continue discarding half and feeding every 12 hours. "
            "Your starter is active when it's bubbly, doubled in size, and floats in water."
        )

    return urgency + action


class SourdoughCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that holds and computes all sourdough state."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self._entry = entry
        self._store: Store = Store(
            hass, STORAGE_VERSION, f"{STORAGE_KEY}.{entry.entry_id}"
        )
        self._stored: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def async_load(self) -> None:
        """Load persisted data from HA storage."""
        stored = await self._store.async_load()
        if stored:
            self._stored = stored
        else:
            self._stored = {
                "start_datetime": dt_util.now().isoformat(),
                "feedings": [],
            }
            await self._store.async_save(self._stored)

    # ------------------------------------------------------------------
    # DataUpdateCoordinator hook
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict[str, Any]:
        return self._compute_state()

    # ------------------------------------------------------------------
    # State computation
    # ------------------------------------------------------------------

    def _config(self) -> dict[str, Any]:
        """Merge entry data and options; options take precedence."""
        merged = dict(self._entry.data)
        merged.update(self._entry.options or {})
        return merged

    def _compute_state(self) -> dict[str, Any]:
        cfg = self._config()
        now = dt_util.now()

        # Parse start datetime
        start_dt = dt_util.parse_datetime(
            self._stored.get("start_datetime", now.isoformat())
        )
        if start_dt is None:
            start_dt = now

        feedings: list[dict] = self._stored.get("feedings", [])

        # Current recipe day (1-indexed, never goes below 1)
        elapsed_seconds = max(0, (now - start_dt).total_seconds())
        current_day = int(elapsed_seconds / 86400) + 1

        # Phase details
        interval_hours, should_discard = _get_phase_for_day(current_day)
        phase_label = _phase_label(current_day)

        # Last feeding
        last_feeding_dt: datetime | None = None
        if feedings:
            last_feeding_dt = dt_util.parse_datetime(feedings[-1]["timestamp"])

        # Next feeding due
        if last_feeding_dt:
            next_feeding_dt = last_feeding_dt + timedelta(hours=interval_hours)
        else:
            next_feeding_dt = start_dt + timedelta(hours=interval_hours)

        # Overdue?
        is_overdue = now > next_feeding_dt
        overdue_minutes = max(0.0, (now - next_feeding_dt).total_seconds() / 60)

        # Configured amounts
        flour_g = float(cfg.get(CONF_FLOUR_AMOUNT, DEFAULT_FLOUR_GRAMS))
        water_g = float(cfg.get(CONF_WATER_AMOUNT, DEFAULT_WATER_GRAMS))
        discard_ratio = float(cfg.get(CONF_DISCARD_RATIO, DEFAULT_DISCARD_RATIO))
        vessel_tare_g = float(cfg.get(CONF_VESSEL_TARE, DEFAULT_VESSEL_TARE_GRAMS))

        # Hydration % (water / flour * 100)
        hydration_pct = (water_g / flour_g * 100) if flour_g > 0 else 100.0

        # Estimated starter weight (excluding vessel)
        starter_weight_g = self._estimate_starter_weight(
            feedings, flour_g, water_g, discard_ratio
        )

        # Discard amount for next feeding
        discard_amount_g = (
            starter_weight_g * discard_ratio if should_discard else 0.0
        )
        starter_after_discard_g = starter_weight_g - discard_amount_g

        instructions = _build_instructions(
            current_day, should_discard, interval_hours, is_overdue, overdue_minutes
        )

        return {
            # Schedule
            "current_day": current_day,
            "phase": phase_label,
            "interval_hours": interval_hours,
            "should_discard": should_discard,
            "is_overdue": is_overdue,
            "overdue_minutes": round(overdue_minutes, 1),
            "last_feeding_dt": last_feeding_dt.isoformat() if last_feeding_dt else None,
            "next_feeding_dt": next_feeding_dt.isoformat(),
            "feeding_count": len(feedings),
            # Weights (grams)
            "flour_g": flour_g,
            "water_g": water_g,
            "discard_ratio": discard_ratio,
            "vessel_tare_g": vessel_tare_g,
            "starter_weight_g": round(starter_weight_g, 1),
            "total_weight_g": round(starter_weight_g + vessel_tare_g, 1),
            "discard_amount_g": round(discard_amount_g, 1),
            "starter_after_discard_g": round(starter_after_discard_g, 1),
            "hydration_pct": round(hydration_pct, 1),
            # Display
            "instructions": instructions,
            # Raw start for display
            "start_datetime": start_dt.isoformat(),
        }

    def _estimate_starter_weight(
        self,
        feedings: list[dict],
        flour_g: float,
        water_g: float,
        discard_ratio: float,
    ) -> float:
        """Estimate current starter weight from feeding history.

        If a weight baseline snapshot exists, it is used as the starting
        point and only feedings recorded *after* the snapshot are replayed.
        Otherwise the replay starts from 0.
        """
        baseline = self._stored.get("weight_baseline")
        if baseline:
            weight = float(baseline["weight_g"])
            baseline_dt = dt_util.parse_datetime(baseline["timestamp"])
            relevant = [
                f for f in feedings
                if dt_util.parse_datetime(f["timestamp"]) > baseline_dt
            ]
        else:
            weight = 0.0
            relevant = feedings

        for feeding in relevant:
            discarded = float(feeding.get("discarded_g", 0.0))
            f_flour = float(feeding.get("flour_g", flour_g))
            f_water = float(feeding.get("water_g", water_g))
            weight = max(0.0, weight - discarded) + f_flour + f_water

        return weight

    # ------------------------------------------------------------------
    # Mutating operations
    # ------------------------------------------------------------------

    async def async_record_feeding(
        self,
        flour_g: float | None = None,
        water_g: float | None = None,
        discarded_g: float | None = None,
        timestamp: datetime | None = None,
    ) -> None:
        """Record a feeding event.

        If amounts are not provided, the configured defaults are used.
        Discard amount defaults to 0 if not provided (caller should pass
        the computed discard_amount if the user discarded).
        If timestamp is provided it is used instead of now(), allowing
        backdating of historical feedings.
        """
        cfg = self._config()
        feeding: dict[str, Any] = {
            "timestamp": (timestamp or dt_util.now()).isoformat(),
            "flour_g": flour_g
            if flour_g is not None
            else float(cfg.get(CONF_FLOUR_AMOUNT, DEFAULT_FLOUR_GRAMS)),
            "water_g": water_g
            if water_g is not None
            else float(cfg.get(CONF_WATER_AMOUNT, DEFAULT_WATER_GRAMS)),
            "discarded_g": discarded_g if discarded_g is not None else 0.0,
        }
        self._stored.setdefault("feedings", []).append(feeding)
        await self._store.async_save(self._stored)
        await self.async_refresh()

    async def async_reset(self) -> None:
        """Restart the sourdough process from Day 1."""
        self._stored = {
            "start_datetime": dt_util.now().isoformat(),
            "feedings": [],
        }
        await self._store.async_save(self._stored)
        await self.async_refresh()

    async def async_set_weight(
        self,
        weight_g: float,
        includes_vessel: bool = True,
    ) -> None:
        """Record a known starter weight, used as the baseline for future estimates.

        Args:
            weight_g: The measured weight in grams.
            includes_vessel: If True, the vessel tare is subtracted before storing
                             so the baseline always represents starter-only weight.
        """
        cfg = self._config()
        tare_g = float(cfg.get(CONF_VESSEL_TARE, 0.0)) if includes_vessel else 0.0
        starter_g = max(0.0, weight_g - tare_g)
        self._stored["weight_baseline"] = {
            "timestamp": dt_util.now().isoformat(),
            "weight_g": round(starter_g, 2),
        }
        await self._store.async_save(self._stored)
        await self.async_refresh()

    async def async_set_day(self, day: int) -> None:
        """Set the current recipe day by backdating the start datetime.

        Sets start_datetime = now - (day - 1) * 24h so that the computed
        current_day equals the requested value.
        """
        if day < 1:
            raise ValueError("Day must be 1 or greater")
        new_start = dt_util.now() - timedelta(hours=(day - 1) * 24)
        self._stored["start_datetime"] = new_start.isoformat()
        await self._store.async_save(self._stored)
        await self.async_refresh()

    async def async_set_start_date(self, start_dt: datetime) -> None:
        """Override the start datetime (useful for backdating)."""
        self._stored["start_datetime"] = start_dt.isoformat()
        await self._store.async_save(self._stored)
        await self.async_refresh()
