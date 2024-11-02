# sensor.py
"""Support for Nature Remo sensors including energy monitoring."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    POWER_WATT,
    ENERGY_KILO_WATT_HOUR,
    PERCENTAGE,
    TEMP_CELSIUS,
    LIGHT_LUX,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class NatureRemoSensorEntityDescription(SensorEntityDescription):
    """Class describing Nature Remo sensor entities."""

    value_fn: Callable[[Any], StateType] | None = None


SENSOR_TYPES: tuple[NatureRemoSensorEntityDescription, ...] = (
    NatureRemoSensorEntityDescription(
        key="power",
        name="Power",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["smart_meter"]["echonetlite_properties"][0]["val"],
    ),
    NatureRemoSensorEntityDescription(
        key="energy",
        name="Energy",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data["smart_meter"]["echonetlite_properties"][1]["val"] / 1000,
    ),
    NatureRemoSensorEntityDescription(
        key="temperature",
        name="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: float(device["newest_events"]["te"]["val"]),
    ),
    NatureRemoSensorEntityDescription(
        key="humidity",
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: float(device["newest_events"]["hu"]["val"]),
    ),
    NatureRemoSensorEntityDescription(
        key="illuminance",
        name="Illuminance",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: float(device["newest_events"]["il"]["val"]),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Nature Remo sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    
    entities: list[SensorEntity] = []

    # Add energy meter sensors
    for appliance in coordinator.data["appliances"].values():
        if appliance["type"] == "EL_SMART_METER":
            entities.extend([
                NatureRemoEnergySensor(
                    coordinator,
                    appliance,
                    description,
                )
                for description in SENSOR_TYPES[:2]  # Power and Energy sensors
            ])

    # Add environmental sensors
    for device in coordinator.data["devices"].values():
        available_sensors = device["newest_events"].keys()
        entities.extend([
            NatureRemoSensor(
                coordinator,
                device,
                description,
            )
            for description in SENSOR_TYPES[2:]  # Environmental sensors
            if description.key in ["temperature", "humidity", "illuminance"]
            and description.key[0:2] in available_sensors
        ])

    async_add_entities(entities)


class NatureRemoSensorBase(CoordinatorEntity, SensorEntity):
    """Base class for Nature Remo sensors."""

    entity_description: NatureRemoSensorEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device: dict[str, Any],
        description: NatureRemoSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._device = device
        
        # Set unique_id based on device ID and sensor type
        self._attr_unique_id = f"{device['id']}_{description.key}"
        
        # Set device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device["id"])},
            "name": device["name"],
            "manufacturer": "Nature",
            "model": device.get("serial_number", "Remo"),
            "sw_version": device.get("firmware_version"),
        }

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        try:
            if self.entity_description.value_fn:
                return self.entity_description.value_fn(self._device)
        except (KeyError, TypeError, ValueError):
            _LOGGER.error(
                "Error getting state for %s sensor %s",
                self.entity_description.key,
                self.name,
            )
        return None


class NatureRemoEnergySensor(NatureRemoSensorBase):
    """Implementation of a Nature Remo energy sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        appliance: dict[str, Any],
        description: NatureRemoSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, appliance["device"], description)
        self._appliance = appliance
        self._attr_name = f"{appliance['nickname']} {description.name}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        try:
            appliance = self.coordinator.data["appliances"][self._appliance["id"]]
            if self.entity_description.value_fn:
                return self.entity_description.value_fn(appliance)
        except (KeyError, TypeError, ValueError):
            _LOGGER.error(
                "Error getting state for %s sensor %s",
                self.entity_description.key,
                self.name,
            )
        return None


class NatureRemoSensor(NatureRemoSensorBase):
    """Implementation of a Nature Remo environmental sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device: dict[str, Any],
        description: NatureRemoSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device, description)
        self._attr_name = f"{device['name']} {description.name}"

# const.py
"""Constants for Nature Remo integration."""
from datetime import timedelta

DOMAIN = "nature_remo"
DEFAULT_UPDATE_INTERVAL = timedelta(seconds=60)

# Sensor endpoints
ENDPOINT_DEVICES = "devices"
ENDPOINT_APPLIANCES = "appliances"

# Energy properties
ECHONET_INSTANT_POWER = 231  # Measured instantaneous power consumption
ECHONET_CUMULATIVE_POWER = 224  # Measured cumulative power consumption
