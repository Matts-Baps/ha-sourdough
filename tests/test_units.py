"""Tests for the unit conversion utilities."""

import pytest

from custom_components.sourdough.units import (
    _fraction_str,
    cups_flour_to_grams,
    cups_water_to_grams,
    format_flour_volume,
    format_weight,
    format_water_volume,
    grams_flour_to_cups,
    grams_to_oz,
    grams_water_to_cups,
    input_to_grams,
    oz_to_grams,
)
from custom_components.sourdough.const import UNIT_IMPERIAL, UNIT_METRIC


class TestWeightConversion:
    def test_grams_to_oz(self):
        assert grams_to_oz(28.3495) == pytest.approx(1.0, rel=1e-3)
        assert grams_to_oz(0) == 0.0
        assert grams_to_oz(100) == pytest.approx(3.53, rel=1e-2)

    def test_oz_to_grams(self):
        assert oz_to_grams(1.0) == pytest.approx(28.35, rel=1e-2)
        assert oz_to_grams(0) == 0.0

    def test_roundtrip(self):
        for g in [30, 60, 120, 200, 500]:
            assert oz_to_grams(grams_to_oz(g)) == pytest.approx(g, rel=1e-4)


class TestVolumeConversion:
    def test_cups_flour_to_grams(self):
        assert cups_flour_to_grams(1.0) == pytest.approx(120.0)
        assert cups_flour_to_grams(0.5) == pytest.approx(60.0)

    def test_cups_water_to_grams(self):
        assert cups_water_to_grams(1.0) == pytest.approx(240.0)
        assert cups_water_to_grams(0.25) == pytest.approx(60.0)

    def test_grams_flour_to_cups(self):
        assert grams_flour_to_cups(120.0) == pytest.approx(1.0)
        assert grams_flour_to_cups(60.0) == pytest.approx(0.5)

    def test_grams_water_to_cups(self):
        assert grams_water_to_cups(240.0) == pytest.approx(1.0)
        assert grams_water_to_cups(60.0) == pytest.approx(0.25)


class TestFormatWeight:
    def test_metric_returns_grams(self):
        value, unit = format_weight(100.0, UNIT_METRIC)
        assert unit == "g"
        assert value == pytest.approx(100.0)

    def test_imperial_returns_oz(self):
        value, unit = format_weight(28.3495, UNIT_IMPERIAL)
        assert unit == "oz"
        assert value == pytest.approx(1.0, rel=1e-3)


class TestFormatVolume:
    def test_half_cup_flour(self):
        result = format_flour_volume(60.0)
        assert "1/2" in result
        assert "cup" in result

    def test_quarter_cup_water(self):
        result = format_water_volume(60.0)
        assert "1/4" in result
        assert "cup" in result

    def test_one_cup_flour(self):
        result = format_flour_volume(120.0)
        assert "cup" in result

    def test_small_flour_uses_tbsp(self):
        # 7.5g = 1 tbsp flour
        result = format_flour_volume(7.5)
        assert "tbsp" in result


class TestFractionStr:
    @pytest.mark.parametrize("frac,expected", [
        (0.5, "1/2"),
        (0.25, "1/4"),
        (0.75, "3/4"),
        (0.125, "1/8"),
        (0.0, ""),   # no fraction
        (0.99, ""),  # too far from any threshold
    ])
    def test_known_fractions(self, frac, expected):
        assert _fraction_str(frac) == expected


class TestInputToGrams:
    def test_metric_passthrough(self):
        assert input_to_grams(60.0, UNIT_METRIC) == 60.0

    def test_imperial_converts_oz(self):
        assert input_to_grams(1.0, UNIT_IMPERIAL) == pytest.approx(28.35, rel=1e-2)
