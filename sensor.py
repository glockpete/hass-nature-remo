"""Support for Nature Remo sensors."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
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
    PERCENTAGE,
    POWER_KILO_WATT,
    POWER_WATT,
    ENERGY_KILO_WATT_HOUR,
    TEMP_CELSIUS,
    LIGHT_LUX,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class NatureRemoSensorEntityDescription(SensorEntityDescription):
    """Class describing Nature Remo sensor entities."""

    value_fn: Callable[[Any], StateType] | None = None


SENSOR_TYPES: tuple[NatureRemoSensorEntityDescription, ...] = (
    # Power sensors
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
    # Environmental sensors
    NatureRemoSensorEntityDescription(
        key="temperature",
        name="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: float(device["newest_events"]["te"]["val"]),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NatureRemoSensorEntityDescription(
        key="humidity",
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: float(device["newest_events"]["hu"]["val"]),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NatureRemoSensorEntityDescription(
        key="illuminance",
        name="Illuminance",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: float(device["newest_events"]["il"]["val"]),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # Device health sensors
    NatureRemoSensorEntityDescription(
        key="wifi_signal",
        name="WiFi Signal",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.get("wifi_strength"),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NatureRemoSensorEntityDescription(
        key="last_updated",
        name="Last Updated",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda device: datetime.fromisoformat(device["updated_at"].replace("Z", "+00:00")),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NatureRemoSensorEntityDescription(
        key="firmware_version",
        name="Firmware Version",
        value_fn=lambda device: device.get("firmware_version"),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Nature Remo sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities: list[SensorEntity] = []

    # Add energy meter sensors
    for appliance in coordinator.data["appliances"].values():
        if appliance["type"] == "EL_SMART_METER":
            entities.extend([
                NatureRemoEnergySensor(coordinator, appliance, description)
                for description in SENSOR_TYPES[:2]  # Power and Energy sensors
            ])

    # Add environmental and device health sensors
    for device in coordinator.data["devices"].values():
        # Skip devices that are already handled as appliances
        if device["id"] in [app["device"]["id"] for app in coordinator.data["appliances"].values()]:
            continue

        # Add available environmental sensors
        available_events = device.get("newest_events", {}).keys()
        for description in SENSOR_TYPES[2:5]:  # Environmental sensors
            if description.key[0:2] in available_events:
                entities.append(NatureRemoSensor(coordinator, device, description))

        # Add device health sensors
        for description in SENSOR_TYPES[5:]:  # Device health sensors
            entities.append(NatureRemoSensor(coordinator, device, description))

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
        
        self._attr_unique_id = f"{device['id']}_{description.key}"
        self._attr_name = f"{device.get('name', 'Nature Remo')} {description.name}"
        
        # Set device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device["id"])},
            "name": device.get("name", "Nature Remo"),
            "manufacturer": "Nature",
            "model": device.get("firmware_version", "Remo"),
            "sw_version": device.get("firmware_version"),
        }

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        try:
            if self.entity_description.value_fn:
                return self.entity_description.value_fn(self._device)
        except (KeyError, TypeError, ValueError) as err:
            _LOGGER.war
