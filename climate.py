"""Support for Nature Remo AC."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityDescription,
    ClimateEntityFeature,
    HVACMode,
    PRESET_ECO,
    PRESET_NONE,
    PRESET_COMFORT,
    PRESET_BOOST,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_WHOLE,
    PRECISION_HALVES,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN
from .const import (
    CONF_COOL_TEMP,
    CONF_HEAT_TEMP,
    DEFAULT_COOL_TEMP,
    DEFAULT_HEAT_TEMP,
)

_LOGGER = logging.getLogger(__name__)

# Map HA modes to Nature Remo modes
MODE_HA_TO_REMO = {
    HVACMode.AUTO: "auto",
    HVACMode.COOL: "cool",
    HVACMode.DRY: "dry",
    HVACMode.FAN_ONLY: "blow",
    HVACMode.HEAT: "warm",
    HVACMode.OFF: "power-off",
}

# Map Nature Remo modes to HA modes
MODE_REMO_TO_HA = {v: k for k, v in MODE_HA_TO_REMO.items()}

# Preset modes mapping
PRESET_MODES = {
    PRESET_NONE: "normal",
    PRESET_ECO: "eco",
    PRESET_COMFORT: "comfort",
    PRESET_BOOST: "boost",
}

@dataclass
class NatureRemoClimateEntityDescription(ClimateEntityDescription):
    """Class describing Nature Remo climate entities."""


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Nature Remo AC."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api = hass.data[DOMAIN][entry.entry_id]["api"]
    config = hass.data[DOMAIN][entry.entry_id]["config"]

    entities = [
        NatureRemoAC(
            coordinator=coordinator,
            api=api,
            appliance=appliance,
            config=config,
        )
        for appliance in coordinator.data["appliances"].values()
        if appliance["type"] == "AC"
    ]

    async_add_entities(entities)


class NatureRemoAC(CoordinatorEntity, ClimateEntity):
    """Implementation of a Nature Remo AC."""

    _attr_has_entity_name = True
    _enable_turn_on_off_backwards_compatibility = False
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    
    def __init__(
        self,
        coordinator,
        api,
        appliance: dict[str, Any],
        config: dict[str, Any],
    ) -> None:
        """Initialize the climate device."""
        super().__init__(coordinator)
        self._api = api
        self._appliance = appliance
        self._attr_unique_id = f"{appliance['id']}_climate"
        self._attr_name = appliance["nickname"]

        # Set device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, appliance["device"]["id"])},
            "name": appliance["nickname"],
            "manufacturer": "Nature",
            "model": appliance.get("model", {}).get("name", "Remo AC"),
            "sw_version": appliance["device"].get("firmware_version"),
        }

        # Default temperatures
        self._default_temps = {
            HVACMode.COOL: config.get(CONF_COOL_TEMP, DEFAULT_COOL_TEMP),
            HVACMode.HEAT: config.get(CONF_HEAT_TEMP, DEFAULT_HEAT_TEMP),
        }

        # Get supported modes and features
        self._modes = appliance["aircon"]["range"]["modes"]
        self._last_mode = None
        self._last_target_temp = {mode: None for mode in MODE_REMO_TO_HA.values()}

        # Initialize states
        self._current_mode = None
        self._target_temperature = None
        self._current_temperature = None
        self._current_fan_mode = None
        self._current_swing_mode = None
        self._current_preset = PRESET_NONE

        # Set supported features
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.SWING_MODE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.PRESET_MODE
        )

        # Update initial state
        self._update_state(appliance["settings"])

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return current operation mode."""
        return self._current_mode

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return available operation modes."""
        modes = [HVACMode.OFF]  # Always include OFF
        for mode in self._modes:
            if mode in MODE_REMO_TO_HA:
                modes.append(MODE_REMO_TO_HA[mode])
        return modes

    @property
    def current_temperature(self) -> float | None:
        """Return current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self) -> float | None:
        """Return target temperature."""
        return self._target_temperature

    @property
    def target_temperature_step(self) -> float:
        """Return supported temperature step."""
        temp_range = self._get_temp_range()
        if len(temp_range) >= 2:
            step = round(temp_range[1] - temp_range[0], 1)
            if step in [0.5, 1.0]:
                return step
        return 1.0

    @property
    def precision(self) -> float:
        """Return temperature precision."""
        return PRECISION_HALVES if self.target_temperature_step == 0.5 else PRECISION_WHOLE

    @property
    def fan_mode(self) -> str | None:
        """Return fan mode."""
        return self._current_fan_mode

    @property
    def fan_modes(self) -> list[str] | None:
        """Return available fan modes."""
        if self._current_mode == HVACMode.OFF:
            return None
        return self._modes[MODE_HA_TO_REMO[self._current_mode]]["vol"]

    @property
    def swing_mode(self) -> str | None:
        """Return swing mode."""
        return self._current_swing_mode

    @property
    def swing_modes(self) -> list[str] | None:
        """Return available swing modes."""
        if self._current_mode == HVACMode.OFF:
            return None
        return self._modes[MODE_HA_TO_REMO[self._current_mode]]["dir"]

    @property
    def preset_mode(self) -> str | None:
        """Return current preset mode."""
        return self._current_preset

    @property
    def preset_modes(self) -> list[str] | None:
        """Return available preset modes."""
        return list(PRESET_MODES.keys())

    @property
    def min_temp(self) -> float:
        """Return minimum temperature."""
        temp_range = self._get_temp_range()
        return min(temp_range) if temp_range else 16.0

    @property
    def max_temp(self) -> float:
        """Return maximum temperature."""
        temp_range = self._get_temp_range()
        return max(temp_range) if temp_range else 30.0

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        if (target_temp := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        # Ensure temperature is within valid range
        target_temp = min(max(target_temp, self.min_temp), self.max_temp)

        # Round to supported precision
        if self.precision == PRECISION_WHOLE:
            target_temp = round(target_temp)

        try:
            await self._api.update_ac_settings(
                self._appliance["id"],
                {"temperature": str(target_temp)},
            )
            self._target_temperature = target_temp
            self._last_target_temp[self._current_mode] = target_temp
            self.async_write_ha_state()
        except Exception as err:
            _LOGGER.error("Failed to set temperature: %s", err)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set operation mode."""
        try:
            if hvac_mode == HVACMode.OFF:
                await self._api.update_ac_settings(
                    self._appliance["id"],
                    {"button": "power-off"},
                )
            else:
                remo_mode = MODE_HA_TO_REMO[hvac_mode]
                settings = {"operation_mode": remo_mode}

                # Set previous or default temperature
                if (prev_temp := self._last_target_temp.get(hvac_mode)) is not None:
                    settings["temperature"] = str(prev_temp)
                elif (default_temp := self._default_temps.get(hvac_mode)) is not None:
                    settings["temperature"] = str(default_temp)

                await self._api.update_ac_settings(
                    self._appliance["id"],
                    settings,
                )
            
            self._current_mode = hvac_mode
            self.async_write_ha_state()
        except Exception as err:
            _LOGGER.error("Failed to set operation mode: %s", err)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode."""
        try:
            await self._api.update_ac_settings(
                self._appliance["id"],
                {"air_volume": fan_mode},
            )
            self._current_fan_mode = fan_mode
            self.async_write_ha_state()
        except Exception as err:
            _LOGGER.error("Failed to set fan mode: %s", err)

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set swing mode."""
        try:
            await self._api.update_ac_settings(
                self._appliance["id"],
                {"air_direction": swing_mode},
            )
            self._current_swing_mode = swing_mode
            self.async_write_ha_state()
        except Exception as err:
            _LOGGER.error("Failed to set swing mode: %s", err)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        if preset_mode not in PRESET_MODES:
            raise ValueError(f"Invalid preset mode: {preset_mode}")
        
        try:
            await self._api.update_ac_settings(
                self._appliance["id"],
                {"button": PRESET_MODES[preset_mode]},
            )
            self._current_preset = preset_mode
            self.async_write_ha_state()
        except Exception as err:
            _LOGGER.error("Failed to set preset mode: %s", err)

    async def async_turn_on(self) -> None:
        """Turn on the AC."""
        # Restore last active mode or use default
        mode = self._last_mode or HVACMode.COOL
        await self.async_set_hvac_mode(mode)

    async def async_turn_off(self) -> None:
        """Turn off the AC."""
        if self._current_mode != HVACMode.OFF:
            self._last_mode = self._current_mode
        await self.async_set_hvac_mode(HVACMode.OFF)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self._appliance["id"] not in self.coordinator.data["appliances"]:
            return

        appliance = self.coordinator.data["appliances"][self._appliance["id"]]
        self._update_state(appliance["settings"])
        
        # Update current temperature if available
        if (device := self.coordinator.data["devices"].get(self._appliance["device"]["id"])):
            try:
                self._current_temperature = float(device["newest_events"]["te"]["val"])
            except (KeyError, ValueError, TypeError):
                self._current_temperature = None

        self.async_write_ha_state()

    def _update_state(self, settings: dict[str, Any]) -> None:
        """Update internal state from settings."""
        # Update operation mode
        button = settings.get("button")
        if button == "power-off":
            self._current_mode = HVACMode.OFF
        else:
            remo_mode = settings.get("mode")
            self._current_mode = MODE_REMO_TO_HA.get(remo_mode, self._current_mode)

        # Update target temperature
        try:
            self._target_temperature = float(settings.get("temp", 0))
            if self._current_mode != HVACMode.OFF:
                self._last_target_temp[self._current_mode] = self._target_temperature
        except (ValueError, TypeError):
            self._target_temperature = None

        # Update fan and swing modes
        self._current_fan_mode = settings.get("vol")
        self._current_swing_mode = settings.get("dir")

        # Update preset mode (if applicable)
        for preset, remo_preset in PRESET_MODES.items():
            if button == remo_preset:
                self._current_preset = preset
                break

    def _get_temp_range(self) -> list[float]:
        """Get available temperature range for current mode."""
        if self._current_mode == HVACMode.OFF:
            return []
        
        remo_mode = MODE_HA_TO_REMO[self._current_mode]
        temp_range = self._modes[remo_mode]["temp"]
        return [float(temp) for temp in temp_range if temp is not None]
