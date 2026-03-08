"""Constants for the Sourdough Monitor integration."""

DOMAIN = "sourdough"
PLATFORMS = ["sensor"]

# Storage
STORAGE_KEY = f"{DOMAIN}.data"
STORAGE_VERSION = 1

# Unit systems
UNIT_METRIC = "metric"
UNIT_IMPERIAL = "imperial"

# Conversion factors
GRAMS_PER_OZ = 28.3495
# Approximate conversions for volume <-> weight
# These vary by flour type; AP flour is ~120g/cup, water is 240g/cup
GRAMS_PER_CUP_FLOUR = 120.0
GRAMS_PER_CUP_WATER = 240.0
GRAMS_PER_TBSP_FLOUR = GRAMS_PER_CUP_FLOUR / 16
GRAMS_PER_TBSP_WATER = GRAMS_PER_CUP_WATER / 16

# Default recipe values (metric, based on 1/2 cup flour + 1/4 cup water)
# 1/2 cup AP flour ≈ 60g; 1/4 cup water ≈ 60g
DEFAULT_FLOUR_GRAMS = 60.0
DEFAULT_WATER_GRAMS = 60.0
DEFAULT_DISCARD_RATIO = 0.5  # discard 50% before each feeding (Day 3+)
DEFAULT_VESSEL_TARE_GRAMS = 0.0

# Recipe phase definitions: (min_day, max_day, interval_hours, discard)
RECIPE_PHASES = [
    (1, 2, 24, False),   # Days 1-2: feed every 24h, no discard
    (3, 5, 24, True),    # Days 3-5: discard half, feed every 24h
    (6, 7, 12, True),    # Days 6-7: discard half, feed every 12h
    (8, 999, 12, True),  # Day 8+: maintenance, every 12h
]

# Configuration keys
CONF_VESSEL_TARE = "vessel_tare_g"
CONF_FLOUR_AMOUNT = "flour_g"
CONF_WATER_AMOUNT = "water_g"
CONF_DISCARD_RATIO = "discard_ratio"
CONF_UNIT_SYSTEM = "unit_system"
CONF_START_DATETIME = "start_datetime"

# Service names
SERVICE_RECORD_FEEDING = "record_feeding"
SERVICE_RESET = "reset_process"
SERVICE_SET_DAY = "set_day"

# Sensor unique ID suffixes
SENSOR_DAY = "day"
SENSOR_PHASE = "phase"
SENSOR_NEXT_FEEDING = "next_feeding"
SENSOR_LAST_FED = "last_fed"
SENSOR_STARTER_WEIGHT = "starter_weight"
SENSOR_TOTAL_WEIGHT = "total_weight"
SENSOR_VESSEL_TARE = "vessel_tare"
SENSOR_FLOUR_TO_ADD = "flour_to_add"
SENSOR_WATER_TO_ADD = "water_to_add"
SENSOR_DISCARD_AMOUNT = "discard_amount"
SENSOR_INSTRUCTIONS = "instructions"
SENSOR_FEEDING_COUNT = "feeding_count"
SENSOR_HYDRATION = "hydration"
