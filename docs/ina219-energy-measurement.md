# INA219 Energy Measurement

Use this when you want to replace the estimated energy section with real measured current.

## What The INA219 Measures

The INA219 is a high-side current sensor. In this project, use it to measure the current drawn by one ESP32 node at a time:

- Node A: ESP32 + two ultrasonic sensors + LoRa transmit
- Node B: ESP32 + two ultrasonic sensors + LoRa receive + six traffic LEDs

## Wiring

Use the optional INA219 I2C pins already reserved in the firmware:

| INA219 pin | Connect to |
| --- | --- |
| `VCC` | ESP32 `3V3` |
| `GND` | ESP32 `GND` |
| `SDA` | `GPIO41` / `J3-8` |
| `SCL` | `GPIO42` / `J3-7` |
| `VIN+` | power bank / supply `+5V` |
| `VIN-` | measured node `5V` input |

The current path must be:

```text
power bank +5V  -> INA219 VIN+
INA219 VIN-    -> measured node 5V
power bank GND -> measured node GND and INA219 GND
```

Important:

- Do not connect `VIN+` and `VIN-` across `5V` and `GND`.
- Use `3V3` for INA219 `VCC` so I2C logic is safe for the ESP32.
- If the current value is negative, swap `VIN+` and `VIN-`.
- Measure Node A and Node B separately unless you have two INA219 modules with different I2C addresses.
- Make sure the measured node is not also being powered by a normal USB cable, because USB `5V` can bypass the INA219 and make the measured current too low.

For serial logging while measuring, use one of these setups:

- best: put the INA219 in series with the USB cable's `5V` line using a USB breakout/cut cable, while leaving USB data lines connected
- good: use a data-only USB cable to the laptop and power the node through the INA219 `5V` path
- acceptable: measure without serial logging, then record the stable average current manually, but say it was a manual INA219 reading

## Firmware Output

After uploading the current firmware, the node will print one of these at startup:

```text
[INA219] ready at 0x40 SDA=41 SCL=42
```

or:

```text
[INA219] not detected at 0x40 SDA=41 SCL=42
```

When the INA219 is detected, the normal summary log includes power data:

```text
power=5.031V/142.6mA/717.5mW
```

You can also type:

```text
power
```

in the serial logger or monitor to print the latest INA219 reading.

## Logging

Use the existing road logger. It now saves these extra CSV columns when power data exists:

- `power_bus_v`
- `power_current_ma`
- `power_mw`

Example:

```powershell
python tools\road_data_logger.py --port COM3 --node node_b --out data\road_sessions\node_b_ina219.csv
```

Let it run for at least 2-3 minutes while the node is doing realistic work.

For the final presentation power graph, the detailed source file is:

```text
data\road_sessions\ina219_power_timeseries_2026-05-20.csv
```

It records Node A and Node B current/power every 30 seconds while the ultrasonic sensors were active, LoRa was running, and Node B traffic LEDs were on.

## Summarize Measured Energy

For one or more INA219 CSV logs:

```powershell
python tools\ina219_energy_summary.py --csv data\road_sessions\node_a_ina219.csv --csv data\road_sessions\node_b_ina219.csv --road-csv data\data_readed\road_26-05-19_crossroads.csv --out data\road_sessions\ina219_energy_summary.txt
```

The summary gives:

- average voltage
- average current
- min/max current
- average power
- measured energy used
- the exact command to regenerate the final evidence report using measured current

## Regenerate Final Evidence Report With INA219 Values

After the summary gives measured average currents, regenerate:

```powershell
python tools\final_evidence_report.py --csv data\data_readed\road_26-05-19_crossroads.csv --node-a-ma <MEASURED_A_MA> --node-b-ma <MEASURED_B_MA> --energy-note "Current values were measured with an INA219 high-side current sensor."
```

This directly answers the mandatory energy-consideration requirement with real instrument measurements.

## Final Presentation Power Graph

Generate the slide-ready time-series graph with:

```powershell
python tools\final_presentation_graphs.py --csv data\data_readed\road_26-05-19_crossroads.csv --power-csv data\road_sessions\ina219_power_timeseries_2026-05-20.csv --out-dir data\data_readed\presentation_graphs
```

The generated graph is:

```text
data\data_readed\presentation_graphs\09_power_consumption_timeseries.png
```

Use this explanation under the graph:

```text
Node B consumes more power because it receives LoRa continuously and drives the traffic LEDs. The peaks occur when ultrasonic polling, LoRa activity, and LED load overlap. The average current changed slightly from the earlier manual summary because the final graph recalculates averages from the 21 plotted INA219 samples.
```
