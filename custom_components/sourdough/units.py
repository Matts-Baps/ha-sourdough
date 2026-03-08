"""Unit conversion utilities for the Sourdough Monitor integration.

All internal values are stored in grams (metric). This module provides
helper functions to convert to/from imperial for display purposes.
"""

from __future__ import annotations

from .const import (
    GRAMS_PER_CUP_FLOUR,
    GRAMS_PER_CUP_WATER,
    GRAMS_PER_OZ,
    GRAMS_PER_TBSP_FLOUR,
    GRAMS_PER_TBSP_WATER,
    UNIT_IMPERIAL,
)


def grams_to_oz(grams: float) -> float:
    """Convert grams to ounces."""
    return round(grams / GRAMS_PER_OZ, 2)


def oz_to_grams(oz: float) -> float:
    """Convert ounces to grams."""
    return round(oz * GRAMS_PER_OZ, 2)


def grams_flour_to_cups(grams: float) -> float:
    """Convert grams of flour to cups (approximate)."""
    return round(grams / GRAMS_PER_CUP_FLOUR, 3)


def cups_flour_to_grams(cups: float) -> float:
    """Convert cups of flour to grams (approximate)."""
    return round(cups * GRAMS_PER_CUP_FLOUR, 1)


def grams_water_to_cups(grams: float) -> float:
    """Convert grams of water to cups."""
    return round(grams / GRAMS_PER_CUP_WATER, 3)


def cups_water_to_grams(cups: float) -> float:
    """Convert cups of water to grams."""
    return round(cups * GRAMS_PER_CUP_WATER, 1)


def format_weight(grams: float, unit_system: str) -> tuple[float, str]:
    """Return (value, unit_string) for display in the given unit system."""
    if unit_system == UNIT_IMPERIAL:
        return grams_to_oz(grams), "oz"
    return round(grams, 1), "g"


def format_flour_volume(grams: float) -> str:
    """Return a human-readable cup/tablespoon description for flour."""
    cups = grams / GRAMS_PER_CUP_FLOUR
    if cups >= 0.5:
        whole = int(cups)
        frac = cups - whole
        parts = []
        if whole:
            parts.append(f"{whole}")
        frac_str = _fraction_str(frac)
        if frac_str:
            parts.append(frac_str)
        return " ".join(parts) + " cup" + ("s" if cups >= 2 else "")
    tbsp = grams / GRAMS_PER_TBSP_FLOUR
    return f"{round(tbsp, 1)} tbsp"


def format_water_volume(grams: float) -> str:
    """Return a human-readable cup/tablespoon description for water."""
    cups = grams / GRAMS_PER_CUP_WATER
    if cups >= 0.25:
        whole = int(cups)
        frac = cups - whole
        parts = []
        if whole:
            parts.append(f"{whole}")
        frac_str = _fraction_str(frac)
        if frac_str:
            parts.append(frac_str)
        return " ".join(parts) + " cup" + ("s" if cups >= 2 else "")
    tbsp = grams / GRAMS_PER_TBSP_WATER
    return f"{round(tbsp, 1)} tbsp"


def _fraction_str(frac: float) -> str:
    """Convert a decimal to a nearest common fraction string."""
    thresholds = [
        (0.875, "7/8"),
        (0.75, "3/4"),
        (0.625, "5/8"),
        (0.5, "1/2"),
        (0.375, "3/8"),
        (0.25, "1/4"),
        (0.125, "1/8"),
    ]
    for threshold, label in thresholds:
        if abs(frac - threshold) < 0.07:
            return label
    return ""


def input_to_grams(value: float, unit_system: str, is_water: bool = False) -> float:
    """Convert user input (oz or grams) to grams for storage.

    When unit_system is imperial, value is in ounces (weight).
    When unit_system is metric, value is in grams.
    """
    if unit_system == UNIT_IMPERIAL:
        return oz_to_grams(value)
    return float(value)


def cups_to_grams(cups: float, is_water: bool) -> float:
    """Convert cups to grams based on ingredient type."""
    if is_water:
        return cups_water_to_grams(cups)
    return cups_flour_to_grams(cups)
