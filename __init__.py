"""The Nature Remo integration."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import async_timeout
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

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
    ERROR_RESPONSE,
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


class NatureRemoAPI:
    """Nature Remo API wrapper."""

    def __init__(self, token: str, session, base_url: str) -> None:
        """Initialize the API."""
        self._token = token
        self._session = session
        self._base_url = base_url
        self._last_api_call = 0

    @property
    def _headers(self) -> dict:
        """Return headers for API calls."""
        return {"Authorization": f"Bearer {self._token}"}

    async def get_all_data(self) -> dict[str, dict[str, Any]]:
        """Get all devices and appliances data."""
        try:
            devices = await self._get_devices()
            appliances = await self._get_appliances()
            
            return {
                "devices": {device["id"]: device for device in devices},
                "appliances": {app["id"]: app for app in appliances}
            }
        except Exception as err:
            _LOGGER.error("Error fetching data from Nature Remo API: %s", err)
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    async def _get_devices(self) -> list[dict[str, Any]]:
        """Get devices from API."""
        try:
            async with async_timeout.timeout(DEFAULT_TIMEOUT):
                async with self._session.get(
                    f"{self._base_url}devices",
                    headers=self._headers,
                ) as response:
                    if response.status == 401:
                        raise Exception(ERROR_AUTH)
                    if response.status != 200:
                        raise Exception(ERROR_RESPONSE)
                    return await response.json()
        except async_timeout.TimeoutError as err:
            raise Exception(ERROR_TIMEOUT) from err
        except Exception as err:
            raise Exception(ERROR_CONNECTION) from err

    async def _get_appliances(self) -> list[dict[str, Any]]:
        """Get appliances from API."""
        try:
            async with async_timeout.timeout(DEFAULT_TIMEOUT):
                async with self._session.get(
                    f"{self._base_url}appliances",
                    headers=self._headers,
                ) as response:
                    if response.status == 401:
                        raise Exception(ERROR_AUTH)
                    if response.status != 200:
                        raise Exception(ERROR_RESPONSE)
                    return await response.json()
        except async_timeout.TimeoutError as err:
            raise Exception(ERROR_TIMEOUT) from err
        except Exception as err:
            raise Exception(ERROR_CONNECTION) from err

    async def update_ac_settings(self, appliance_id: str, settings: dict[str, Any]) -> None:
        """Update AC settings."""
        params = {k: str(v) for k, v in settings.items()}
        
        try:
            async with async_timeout.timeout(DEFAULT_TIMEOUT):
                async with self._session.post(
                    f"{self._base_url}appliances/{appliance_id}/aircon_settings",
                    headers=self._headers,
                    params=params,
                ) as response:
                    if response.status == 401:
                        raise Exception(ERROR_AUTH)
                    if response.status != 200:
                        raise Exception(ERROR_RESPONSE)
                    return await response.json()
        except async_timeout.TimeoutError as err:
            raise Exception(ERROR_TIMEOUT) from err
        except Exception as err:
            raise Exception(ERROR_CONNECTION) from err


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

    async def async_update_data() -> dict[str, Any]:
        """Fetch data from API."""
        try:
            async with async_timeout.timeout(DEFAULT_TIMEOUT):
                return await api.get_all_data()
        except Exception as err:
            _LOGGER.error("Error communicating with API: %s", err)
            raise UpdateFailed(f"Error communicating with API: {err}") from err

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
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def device_info(self) -> dict[str, Any]:
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

    def __init__(self, coordinator: DataUpdateCoordinator, device: dict[str, Any]) -> None:
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
        return (
            super().available
            and self._device_id in self.coordinator.data["devices"]
        )
