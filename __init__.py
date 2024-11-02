"""The Nature Remo integration."""
from __future__ import annotations

import logging
from datetime import timedelta

import async_timeout
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DOMAIN,
    CONF_ACCESS_TOKEN,
    CONF_COOL_TEMP,
    CONF_HEAT_TEMP,
    DEFAULT_COOL_TEMP,
    DEFAULT_HEAT_TEMP,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_TIMEOUT,
    API_ENDPOINT,
    ERROR_AUTH,
    ERROR_CONNECTION,
    ERROR_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.LIGHT,
    Platform.MEDIA_PLAYER,
]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_ACCESS_TOKEN): cv.string,
                vol.Optional(CONF_COOL_TEMP, default=DEFAULT_COOL_TEMP): vol.Coerce(int),
                vol.Optional(CONF_HEAT_TEMP, default=DEFAULT_HEAT_TEMP): vol.Coerce(int),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Nature Remo component."""
    hass.data.setdefault(DOMAIN, {})

    if DOMAIN not in config:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "import"},
            data=config[DOMAIN],
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nature Remo from a config entry."""
    session = async_get_clientsession(hass)
    
    api = NatureRemoAPI(
        entry.data[CONF_ACCESS_TOKEN],
        session,
        API_ENDPOINT
    )

    async def async_update_data():
        """Fetch data from API."""
        try:
            async with async_timeout.timeout(DEFAULT_TIMEOUT):
                data = await api.get_all_data()
                return data
        except Exception as err:
            _LOGGER.error("Error communicating with API: %s", err)
            raise ConfigEntryNotReady from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_coordinator",
        update_method=async_update_data,
        update_interval=DEFAULT_UPDATE_INTERVAL,
    )

    # Initial data fetch
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "api": api,
        "config": entry.data,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class NatureRemoBase(Entity):
    """Nature Remo base entity class."""

    def __init__(self, coordinator: DataUpdateCoordinator, device_id: str) -> None:
        """Initialize the entity."""
        self.coordinator = coordinator
        self._device_id = device_id
        self._device = coordinator.data["devices"][device_id]

    @property
    def should_poll(self) -> bool:
        """No polling needed for Nature Remo."""
        return False

    @property
    def device_info(self) -> dict:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device.get("name", "Nature Remo Device"),
            "manufacturer": "Nature",
            "model": self._device.get("firmware_version", "Remo"),
            "sw_version": self._device.get("firmware_version"),
        }

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


class NatureRemoDeviceBase(NatureRemoBase):
    """Nature Remo device base entity class."""

    def __init__(self, coordinator: DataUpdateCoordinator, device: dict) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, device["id"])
        self._attr_name = f"Nature Remo {device['name']}"
        self._device = device

    @property
    def unique_id(self) -> str:
        """Return unique ID for the entity."""
        return self._device["id"]

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        device = self.coordinator.data["devices"].get(self._device["id"])
        return device is not None
