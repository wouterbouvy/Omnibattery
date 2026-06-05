# Main sensor

The first step configures the global data sources for the integration.

## Grid consumption sensor

A Home Assistant sensor that measures power exchange with the grid (in **W** or **kW**).

!!! tip "Compatible sensors"
    Any sensor that exposes grid power works: Shelly EM, Shelly EM3, Neurio, smart meter integrations (e.g. `sensor.grid_power`).

!!! warning "Update frequency"
    The sensor should update as fast as possible. The controller is **event-driven** — it recalculates each time this sensor publishes a new value — so the sensor's update rate *is* the control rate: a faster sensor means a faster, more accurate response. (A 2-second watchdog still runs the cycle if the sensor goes quiet.)

    Home consumption can vary by several kilowatts in fractions of a second (appliance start-ups, oven, washing machine…). A sensor that reports every 10 seconds or more introduces a lag that causes the controller to react to a situation that no longer exists, leading to overshoot or unnecessary corrections.

    **Recommended: 1–2 second update interval.** Devices like Shelly EM/EM3 support this natively.

### Automatic kW detection

If the sensor's `unit_of_measurement` attribute is `kW`, the integration multiplies the value by 1000 automatically.

### Inverted sign

Enable **"Inverted meter sign"** if your sensor uses the opposite convention:

| Convention | Import | Export |
|---|---|---|
| Standard (default) | Positive value | Negative value |
| Inverted | Negative value | Positive value |

Leave it disabled if you are unsure.

---

## Solar forecast sensor *(optional)*

Sensor providing today's estimated solar production in **kWh** or **Wh**.

Configuring it here makes it available to:

- **Predictive charging** (Time Slot and Dynamic Pricing modes)
- **Solar charge delay**

You can also leave it blank and configure it later in those specific sections.

---

## Household consumption sensor *(optional)*

A power sensor (W or kW) that measures total household electricity consumption.

This sensor is **optional and acts as a precision override**. By default the integration already derives your home consumption from the values it has (`grid + battery AC + solar`), so predictive charging and charge delay work without it. Configuring a dedicated sensor just replaces the derived value with a direct reading.

**When to configure it:**

- You have a clamp meter, Shelly EM, or similar device measuring total house load.
- You want a direct measurement instead of the derived one (e.g. your grid/solar sensors are noisy).

**How it works:**

| Mode | Consumption source |
|------|-------------------|
| Sensor configured | Integration of the power sensor (W→kWh) during the solar+battery window |
| No sensor (default) | Derived home consumption: `grid + battery AC + solar` (same value as the Home Consumption sensor) |

In both modes the integration accumulates energy during the solar+battery window only (i.e. outside the configured charging time slot). If no time slot is configured, it accumulates all day. The counter resets at midnight and survives HA restarts.

The daily consumption figure feeds the same history that predictive charging and charge delay read — no additional configuration is needed in those sections.

!!! tip "Supported units"
    Both **W** and **kW** sensors are accepted. The integration reads the `unit_of_measurement` attribute and converts automatically.

### Creating a helper sensor

!!! note
    The integration already derives home consumption from this exact balance, so a helper sensor is **not required**. Build one only if you want a standalone entity or a direct hardware measurement to override the derived value.

Household consumption is the balance of all power flows:

**House consumption = Grid power + Solar power + Battery discharge − Battery charge**

Without the battery term, charging would undercount consumption and discharging would overcount it.

If your meter and battery expose these as separate sensors, combine them using a **Template helper** in Home Assistant.

**Go to:** Settings → Devices & Services → Helpers → Create Helper → Template → Template sensor

```jinja
{% set grid_power    = states('sensor.YOUR_GRID_POWER_SENSOR') | float(0) %}
{% set solar_power   = states('sensor.YOUR_SOLAR_POWER_SENSOR') | float(0) %}
{% set bat_discharge = states('sensor.YOUR_BATTERY_DISCHARGE_SENSOR') | float(0) %}
{% set bat_charge    = states('sensor.YOUR_BATTERY_CHARGE_SENSOR') | float(0) %}
{{ (grid_power + solar_power + bat_discharge - bat_charge) | round(0) }}
```

| Variable | Description | Example entity |
|---|---|---|
| `grid_power` | Grid exchange (positive = import, negative = export) | `sensor.shellypro3em_energy_meter_2_power` |
| `solar_power` | Total solar production | `sensor.shellypro3em_energy_meter_1_power` |
| `bat_discharge` | Battery discharge power (positive, W) | `sensor.marstek_venus_system_system_discharge_power` |
| `bat_charge` | Battery charge power (positive, W) | `sensor.marstek_venus_system_system_charge_power` |

Set the **unit of measurement** to `W` and the **device class** to `power`.

!!! tip "Multiple solar strings"
    If you have more than one inverter or solar branch and no single aggregated sensor, sum them:
    ```jinja
    {% set solar_power = states('sensor.SOLAR_STRING_1') | float(0) + states('sensor.SOLAR_STRING_2') | float(0) %}
    ```

![Main sensor configuration](../assets/screenshots/configuration/main-sensor.png){ width="600"  style="display: block; margin: 0 auto;"}
