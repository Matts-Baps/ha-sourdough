# Sourdough Monitor — Home Assistant Integration

A Home Assistant custom integration (installable via HACS) that helps you monitor and manage your sourdough starter. Track feeding schedules, weights, discard amounts, and get plain-text instructions for each stage of the recipe.

---

## Features

- **Recipe-aware schedule** — automatically tracks Days 1–7+ and switches between 24-hour and 12-hour feeding intervals at the right time.
- **Vessel/jar tare tracking** — enter your empty jar weight so the integration can calculate starter-only weight from a scale reading.
- **Metric & Imperial** — configure in either system; all data is stored in grams and converted for display.
- **Custom ratios** — override the default flour/water amounts and discard ratio to match your own recipe.
- **Persistent storage** — feeding history survives Home Assistant restarts.
- **Services** — record feedings and reset the process from automations or the UI.

---

## Installation via HACS

1. Open HACS → **Integrations** → click the three-dot menu → **Custom repositories**.
2. Add `https://github.com/Matts-Baps/ha-sourdough` as an **Integration**.
3. Search for **Sourdough Monitor** and install it.
4. Restart Home Assistant.
5. Go to **Settings → Devices & Services → Add Integration** and search for **Sourdough Monitor**.

---

## Configuration

During setup you will be asked for:

| Field | Description | Default |
|-------|-------------|---------|
| Unit System | Metric (g) or Imperial (oz) for display | Metric |
| Flour per feeding | Amount of flour added at each feeding | 60 g (½ cup) |
| Water per feeding | Amount of water added at each feeding | 60 g (¼ cup) |
| Vessel tare weight | Weight of your empty jar/container | 0 (disabled) |
| Discard ratio | Fraction discarded before feeding on Day 3+ | 0.5 (50%) |

All of these can be changed later via **Configure** on the integration card.

---

## Sensors

| Entity | Description |
|--------|-------------|
| `sensor.sourdough_current_day` | Recipe day number |
| `sensor.sourdough_phase` | Initialization / Establishment / Activation / Maintenance |
| `sensor.sourdough_next_feeding_due` | Timestamp when the next feeding is due |
| `sensor.sourdough_last_fed` | Timestamp of the most recent recorded feeding |
| `sensor.sourdough_starter_weight` | Estimated starter weight (excluding vessel) |
| `sensor.sourdough_total_weight_with_vessel` | Starter + vessel tare weight |
| `sensor.sourdough_vessel_tare_weight` | Configured empty vessel weight |
| `sensor.sourdough_flour_to_add` | Flour amount for the next feeding |
| `sensor.sourdough_water_to_add` | Water amount for the next feeding |
| `sensor.sourdough_discard_amount` | How much starter to discard before feeding |
| `sensor.sourdough_hydration` | Water/flour ratio as a percentage |
| `sensor.sourdough_total_feedings` | Count of feedings recorded |
| `sensor.sourdough_instructions` | Plain-text instructions for the current step |

Weight sensors include both grams and ounces as extra attributes, regardless of the configured unit system. Flour/water sensors also include a `volume_hint` attribute (e.g., `"1/2 cup"`) for convenience.

---

## Services

### `sourdough.record_feeding`

Record that you have fed your starter. Call this after each feeding.

```yaml
service: sourdough.record_feeding
data:
  # All fields are optional — omit to use configured defaults
  flour: 60       # grams (or oz if configured for imperial)
  water: 60       # grams (or oz if configured for imperial)
  discarded: 60   # grams (or oz) — omit on Days 1 & 2
```

### `sourdough.reset_process`

Restart from Day 1 with an empty feeding log.

```yaml
service: sourdough.reset_process
```

If you have multiple sourdough trackers, add `entry_id` to target a specific one.

---

## Automation Examples

### Alert when feeding is overdue

```yaml
automation:
  - alias: "Sourdough feeding overdue"
    trigger:
      - platform: template
        value_template: "{{ state_attr('sensor.sourdough_next_feeding_due', 'is_overdue') }}"
    action:
      - service: notify.mobile_app_your_phone
        data:
          message: >
            Your sourdough starter needs feeding!
            {{ states('sensor.sourdough_instructions') }}
```

### Record feeding via a dashboard button

```yaml
script:
  feed_sourdough:
    alias: "Feed Sourdough"
    sequence:
      - service: sourdough.record_feeding
        data:
          discarded: >
            {{ states('sensor.sourdough_discard_amount') | float }}
```

---

## Recipe Reference

The default schedule follows this recipe:

| Days | Interval | Discard? | Action |
|------|----------|----------|--------|
| 1–2  | 24 h     | No       | Mix flour + water |
| 3–5  | 24 h     | Yes (50%)| Discard half, then feed |
| 6–7  | 12 h     | Yes (50%)| Discard half, then feed twice per day |
| 8+   | 12 h     | Yes (50%)| Maintenance — continue until active |

**Signs your starter is active:** bubbly, doubled or tripled in size, and floats in water.

Default amounts: **½ cup flour (60 g)** + **¼ cup water (60 g)** = 100% hydration.

---

## Unit Conversion Reference

| Volume | Flour (AP) | Water |
|--------|-----------|-------|
| 1 cup | ~120 g / 4.2 oz | 240 g / 8.5 oz |
| ½ cup | ~60 g / 2.1 oz | 120 g / 4.2 oz |
| ¼ cup | ~30 g / 1.1 oz | 60 g / 2.1 oz |
| 1 tbsp | ~7.5 g | 15 g |

*Flour weight varies slightly by type and scooping method. AP flour is used as the reference.*

---

## Recipe Credit

The default feeding schedule is based on the sourdough starter recipe by
[@anabelle.vangiller](https://www.instagram.com/anabelle.vangiller/) on Instagram:
[https://www.instagram.com/p/DSxZ-QKDi7W/](https://www.instagram.com/p/DSxZ-QKDi7W/)

---

## Contributing

Issues and pull requests welcome at `https://github.com/Matts-Baps/ha-sourdough`.

---

## Disclaimer

This integration was written using [Claude Code](https://claude.com/claude-code) (Anthropic's AI coding assistant) and has been reviewed and approved by human maintainers before publication. All logic, schedules, and defaults have been checked for correctness, but as with any community integration, use it at your own discretion.
