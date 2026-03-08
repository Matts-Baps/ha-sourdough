# Sourdough Monitor — Home Assistant Integration

Created by [Matt's Baps](https://www.instagram.com/mattsbaps/) — follow along on Instagram for baking inspiration, recipes, and the sourdough journey that inspired this integration.

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

### Notify when a feeding is due

Triggers at the exact moment the next feeding time is reached.

```yaml
automation:
  - alias: "Sourdough — feeding due"
    trigger:
      - platform: time
        at: sensor.sourdough_next_feeding_due
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "🍞 Sourdough needs feeding"
          message: "{{ states('sensor.sourdough_instructions') }}"
```

### Escalating alert when a feeding is overdue

Reminds you every 30 minutes once the feeding window has passed.

```yaml
automation:
  - alias: "Sourdough — feeding overdue reminder"
    trigger:
      - platform: template
        value_template: "{{ state_attr('sensor.sourdough_phase', 'is_overdue') }}"
        for:
          minutes: 30
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "⚠️ Sourdough overdue"
          message: >
            Feeding overdue by
            {{ (state_attr('sensor.sourdough_phase', 'overdue_minutes') | int) // 60 }}h
            {{ (state_attr('sensor.sourdough_phase', 'overdue_minutes') | int) % 60 }}m.
            {{ states('sensor.sourdough_instructions') }}
```

### Announce on a smart speaker when feeding is due

```yaml
automation:
  - alias: "Sourdough — speaker announcement"
    trigger:
      - platform: time
        at: sensor.sourdough_next_feeding_due
    action:
      - service: tts.speak
        target:
          entity_id: media_player.kitchen_speaker
        data:
          message: "Time to feed your sourdough starter. {{ states('sensor.sourdough_instructions') }}"
```

### Record a feeding from a dashboard button

Use alongside the built-in **Record Feeding** button entity, or call the service directly from a script.

```yaml
script:
  feed_sourdough:
    alias: "Feed Sourdough"
    sequence:
      - service: sourdough.record_feeding
        data:
          discarded: "{{ states('sensor.sourdough_discard_amount') | float }}"
```

### Flash a light when feeding is due

Handy if you want a physical reminder without your phone.

```yaml
automation:
  - alias: "Sourdough — light reminder"
    trigger:
      - platform: time
        at: sensor.sourdough_next_feeding_due
    action:
      - repeat:
          count: 3
          sequence:
            - service: light.turn_on
              target:
                entity_id: light.kitchen
              data:
                color_name: orange
            - delay: "00:00:02"
            - service: light.turn_off
              target:
                entity_id: light.kitchen
            - delay: "00:00:02"
```

### Daily summary notification

Get a morning briefing on your starter's status.

```yaml
automation:
  - alias: "Sourdough — daily summary"
    trigger:
      - platform: time
        at: "08:00:00"
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "🍞 Sourdough update"
          message: >
            Day {{ states('sensor.sourdough_current_day') }}
            ({{ states('sensor.sourdough_phase') }}).
            Next feeding: {{ states('sensor.sourdough_next_feeding_due') | as_timestamp | timestamp_custom('%H:%M') }}.
            Starter weight: {{ states('sensor.sourdough_starter_weight') }}{{ state_attr('sensor.sourdough_starter_weight', 'unit_of_measurement') }}.
```

### Log feedings to a helper for history tracking

Create a **Text** helper (`input_text.sourdough_log`) in HA, then append to it on every feeding.

```yaml
automation:
  - alias: "Sourdough — log feeding"
    trigger:
      - platform: state
        entity_id: sensor.sourdough_total_feedings
    action:
      - service: input_text.set_value
        target:
          entity_id: input_text.sourdough_log
        data:
          value: >
            Last fed {{ now().strftime('%d %b %H:%M') }},
            Day {{ states('sensor.sourdough_current_day') }},
            {{ states('sensor.sourdough_starter_weight') }}g starter.
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
