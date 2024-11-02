
# Home Assistant integration for Nature Remo

A custom [Home Assistant](https://www.home-assistant.io) component for [Nature Remo](https://en.nature.global/en/).

⚠️ This integration is neither Nature Remo official nor Home Assistant official. **Use at your own risk.** ⚠️

<img src="./assets/screenshot_1.png" width="600"><img src="./assets/screenshot_2.png" width="200">

## Supported Features

- [x] Air Conditioner
  - [x] Set mode (e.g., cool, warm, blow, etc.)
  - [x] Set temperature
  - [x] Set fan mode
  - [x] Set swing mode
  - [x] Show current temperature
  - [x] Remember previous target temperatures when switching modes
- [x] Energy Sensor (Nature Remo E/E Lite)
  - [x] Fetch current power usage
- [x] Switch
- [x] Light
- [x] TV
- [x] Sensor Support
  - **Environmental Sensors**:
    - Temperature (°C)
    - Humidity (%)
    - Illuminance (lux)
    - Historical data tracking
    - Configurable update intervals
  - **Energy Monitoring (Nature Remo E/E Lite)**:
    - Real-time power consumption (W)
    - Cumulative energy usage (kWh)
    - Energy cost calculations
    - Integration with Home Assistant Energy Dashboard
  - **Device Health Monitoring**:
    - WiFi signal strength
    - Device last update time
    - Firmware version
    - Connection status

### Sensor Features

- Automatic sensor discovery
- Real-time updates
- Historical data storage
- Energy dashboard integration
- Customizable update intervals
- Multiple unit support
- Diagnostic information

## Sensor Configuration Examples

```yaml
# Example automation using temperature sensor
automation:
  - alias: "High Temperature Alert"
    trigger:
      platform: numeric_state
      entity_id: sensor.nature_remo_temperature
      above: 28
    action:
      - service: notify.mobile_app
        data:
          message: "Temperature is too high!"

# Example template sensor for energy cost calculation
template:
  - sensor:
      - name: "Daily Energy Cost"
        unit_of_measurement: "USD"
        state: >
          {% set kwh_price = 0.15 %}
          {{ states('sensor.nature_remo_energy') | float * kwh_price }}
```

### Sensor Statistics

```yaml
# Example history/statistics configuration
history:
  include:
    entities:
      - sensor.nature_remo_temperature
      - sensor.nature_remo_humidity
      - sensor.nature_remo_illuminance
      - sensor.nature_remo_power
      - sensor.nature_remo_energy

# Example utility meter configuration for daily energy tracking
utility_meter:
  daily_energy:
    source: sensor.nature_remo_energy
    cycle: daily
```

## Sensor Troubleshooting

### Common Sensor Issues

1. **Inaccurate Temperature Readings**:
   - Ensure the device is not placed near heat sources
   - Allow 15-30 minutes for readings to stabilize
   - Check for direct sunlight exposure

2. **Missing Energy Data**:
   - Verify Nature Remo E/E Lite connection
   - Check power meter configuration
   - Ensure proper wiring installation

3. **Delayed Sensor Updates**:
   - Check WiFi signal strength
   - Verify network connectivity
   - Adjust update interval if needed

### Best Practices for Sensors

1. **Placement**:
   - Keep away from heat sources
   - Avoid direct sunlight
   - Maintain clear line of sight
   - Consider room air circulation

2. **Energy Monitoring**:
   - Regular calibration checks
   - Compare with utility meter
   - Monitor update frequency
   - Track historical data

3. **Maintenance**:
   - Clean sensors periodically
   - Check WiFi connection
   - Update firmware when available
   - Verify sensor accuracy

## Installation

### Manual Install

1. Download this repository
2. Create a `custom_components/nature_remo` folder in your config directory
3. Copy the files into it

```
{path_to_your_config}
├── configuration.yaml
└── custom_components
    └── nature_remo
        ├── __init__.py
        ├── climate.py
        ├── manifest.json
        └── sensor.py
```

### Install via git submodule

If you have set up git, you can also install this component by adding a submodule to your git repository.

```sh
git submodule add https://github.com/yutoyazaki/hass-nature-remo.git {path_to_custom_component}/nature_remo
```

## Configuration

1. Go to https://home.nature.global and sign in/up
2. Generate an access token
3. Add the following code to your `configuration.yaml` file

```yaml
nature_remo:
  access_token: YOUR_ACCESS_TOKEN
```
