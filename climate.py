"""Support for Nature Remo AC."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode
from homeassistant.components.climate.const import (
    ATTR_HVAC_MODE,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    SWING_OFF,
    SWING_ON,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NatureRemoBase
from .const import (
    DOMAIN,
    CONF_COOL_TEMP,
    CONF_HEAT_TEMP,
    DEFAULT_COOL_TEMP,
    DEFAULT_HEAT_TEMP,
    TYPE_AC,
    MODE_MAP,
    ATTR_OPERATION_MODE,
    ATTR_TARGET_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_SWING_MODE,
)

_LOGGER = logging.getLogger(__name__)

# Map HA modes to Nature Remo modes
MODE_HA_TO_REMO = {
    HVACMode.AUTO: MODE_MAP["auto"],
    HVACMode.COOL: MODE_MAP["cool"],
    HVACMode.HEAT: MODE_MAP["warm"],
    HVACMode.DRY: MODE_MAP["dry"],
    HVACMode.FAN_ONLY: MODE_MAP["blow"],
    HVACMode.OFF: MODE_MAP["off"],
}

# Map Nature Remo modes to HA modes
MODE_REMO_TO_HA = {v: k for k, v in MODE_HA_TO_REMO.items()}

SUPPORT_FLAGS = (
    ClimateEntityFeature.TARGET_TEMPERATURE
    | ClimateEntityFeature.FAN_MODE
    | ClimateEntityFeature.SWING_MODE
    | ClimateEntityFeature.TURN_ON
    | ClimateEntityFeature.TURN_OFF
)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Nature Remo AC."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api = hass.data[DOMAIN][entry.entry_id]["api"]
    config = hass.data[DOMAIN][entry.entry_id]["config"]

    async_add_entities(
        [
            NatureRemoAC(coordinator, api, appliance, config)
            for appliance in coordinator.data["appliances"].values()
            if appliance["type"] == TYPE_AC
        ]
    )


class NatureRemoAC(NatureRemoBase, ClimateEntity):
    """Implementation of a Nature Remo AC."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, coordinator, api, appliance, config):
        """Initialize the AC."""
        super().__init__(coordinator, appliance["device"]["id"])
        self._api = api
        self._appliance = appliance
        self._attr_unique_id = f"{appliance['id']}_climate"
        self._attr_name = appliance["nickname"]

        # Get default temperatures from config
        self._default_temps = {
            HVACMode.COOL: config.get(CONF_COOL_TEMP, DEFAULT_COOL_TEMP),
            HVACMode.HEAT: config.get(CONF_HEAT_TEMP, DEFAULT_HEAT_TEMP),
        }

        # Initialize state
        self._attr_supported_features = SUPPORT_FLAGS
        self._modes = appliance["aircon"]["range"]["modes"]
        self._hvac_mode = None
        self._current_temp = None
        self._target_temp = None
        self._remo_mode = None
        self._fan_mode = None
        self._swing_mode = None
        self._last_target_temp = {v: None for v in MODE_REMO_TO_HA}

        self._update_state(appliance["settings"])

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return hvac operation ie. heat, cool mode."""
        return self._hvac_mode

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available hvac operation modes."""
        modes = [HVACMode.OFF]  # Always include OFF
        for mode in self._modes:
            if mode in MODE_REMO_TO_HA:
                modes.append(MODE_REMO_TO_HA[mode])
        return modes

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._current_temp

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._target_temp

    @property
    def target_temperature_step(self) -> float:
        """Return the supported step of target temperature."""
        if self._hvac_mode == HVACMode.OFF:
            return 1.0
        
        temp_range = self._get_temp_range()
        if len(temp_range) >= 2:
            step = round(temp_range[1] - temp_range[0], 1)
            return step if step in [0.5, 1.0] else 1.0
        return 1.0

    # Rest of the class methods...
    # Add similar updates to other methods using the new constants
