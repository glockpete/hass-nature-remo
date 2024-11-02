"""The Nature Remo integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import async_timeout
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    Platform,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant, Event
from homeassistant.exceptions import ConfigEntryNotReady, ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import (
    NatureRemoAPI,
    NatureRemoAuthError,
    NatureRemoConnectionError,
    NatureRemoError,
)
from .const import (
    DOMAIN,
    CONF_COOL_TEMP,
    CONF_HEAT_TEMP,
    DEFAULT_COOL_TEMP,
    DEFAULT_HEAT_TEMP,
    DEFAULT_TIMEOUT,
    DEFAULT_UPDATE_INTERVAL,
    MANUFACTURER,
    MODEL_MAP,
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
                vol.Required(CONF_ACCESS_TOKEN): str,
                vol.Optional(CONF_COOL_TEMP, default=DEFAULT_COOL_TEMP): vol.Coerce(int),
                vol.Optional(CONF_HEAT_TEMP, default=DEFAULT_HEAT_TEMP): vol.Coerce(int),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Nature Remo domain."""
    hass.data.setdefault(DOMAIN, {})

    if DOMAIN not in config:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config[DOMAIN],
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nature Remo from a config entry."""
    session = async_get_clientsession(hass)
    api = NatureRemoAPI(entry.data[CONF_ACCESS_TOKEN], session)

    async def async_update_data() -> dict[str, Any]:
        """Fetch data from API."""
        try:
            async with async_timeout.timeout(DEFAULT_TIMEOUT):
                return await api.get_all_data()
        except NatureRemoAuthError as err:
            raise ConfigEntryAuthFailed from err
        except NatureRemoConnectionError as err:
            raise UpdateFailed(f"Error communicating with API: {err}")
        except NatureRemoError as err:
            raise UpdateFailed(f"Error fetching data: {err}")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_coordinator",
        update_method=async_update_data,
        update_interval=DEFAULT_UPDATE_INTERVAL,
    )

    # Fetch initial data to check connection and validate setup
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryAuthFailed:
        _LOGGER.error("Invalid authentication")
        return False
    except ConfigEntryNotReady:
        raise

    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
        "config": entry.data,
        "unsub_stop": None,  # Will store the stop event listener
    }

    # Register devices
    await _async_register_devices(hass, entry, coordinator.data)

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Set up event listener for cleanup
    async def async_stop(event: Event) -> None:
        """Handle cleanup when Home Assistant stops."""
        await api.close_session()

    hass.data[DOMAIN][entry.entry_id]["unsub_stop"] = hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, async_stop
    )

    # Register update listener for config entry changes
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Clean up
        data = hass.data[DOMAIN].pop(entry.entry_id)
        # Remove stop event listener
        if data["unsub_stop"] is not None:
            data["unsub_stop"]()
        # Close API session
        await data["api"].close_session()

    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", entry.version)

    if entry.version == 1:
        new_data = {**entry.data}
        
        # Add new default values
        new_data.setdefault(CONF_COOL_TEMP, DEFAULT_COOL_TEMP)
        new_data.setdefault(CONF_HEAT_TEMP, DEFAULT_HEAT_TEMP)

        entry.version = 2
        hass.config_entries.async_update_entry(entry, data=new_data)

    _LOGGER.info("Migration to version %s successful", entry.version)

    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_register_devices(
    hass: HomeAssistant,
    entry: ConfigEntry,
    data: dict[str, Any],
) -> None:
    """Register devices with the device registry."""
    device_registry = dr.async_get(hass)

    # Register the Nature Remo hub device
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "nature_remo_hub")},
        manufacturer=MANUFACTURER,
        name="Nature Remo Hub",
        model="Hub",
        sw_version=entry.data.get("hub_version"),
    )

    # Register all physical Nature Remo devices
    for device in data["devices"].values():
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, device["id"])},
            manufacturer=MANUFACTURER,
            name=device.get("name", "Nature Remo Device"),
            model=MODEL_MAP.get(device.get("firmware_version", "")).get("name", "Unknown"),
            sw_version=device.get("firmware_version"),
            via_device=(DOMAIN, "nature_remo_hub"),
        )

    # Register IR-controlled appliances
    for appliance in data["appliances"].values():
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, appliance["id"])},
            manufacturer=appliance.get("model", {}).get("manufacturer", "Unknown"),
            name=appliance.get("nickname", "IR Device"),
            model=appliance.get("model", {}).get("name", "Unknown"),
            via_device=(DOMAIN, appliance["device"]["id"]),
        )


class NatureRemoEntity(CoordinatorEntity):
    """Base class for Nature Remo entities."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_id: str,
        name: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_name = name
        self._attr_unique_id = f"{device_id}_{self.__class__.__name__.lower()}"
        self._attr_device_info = self._get_device_info()

    def _get_device_info(self) -> dict[str, Any]:
        """Get device info."""
        device = self.coordinator.data["devices"].get(self._device_id, {})
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": device.get("name", self._attr_name),
            "manufacturer": MANUFACTURER,
            "model": MODEL_MAP.get(device.get("firmware_version", "")).get("name", "Unknown"),
            "sw_version": device.get("firmware_version"),
            "via_device": (DOMAIN, "nature_remo_hub"),
        }

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        device = self.coordinator.data["devices"].get(self._device_id)
        if device and "updated_at" in device:
            last_update = datetime.fromisoformat(device["updated_at"].replace("Z", "+00:00"))
            # Consider device unavailable if not updated in last hour
            if (datetime.now() - last_update).total_seconds() > 3600:
                return False
        return super().available
