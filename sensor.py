"""Support for Nature Remo sensors."""
from __future__ import annotations

from dataclasses import dataclass
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
    POWER_WATT,
    ENERGY_KILO_WATT_HOUR,
    UnitOfTemperature,
    LIGHT_LUX,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import NatureRemoBase, NatureRemoDeviceBase
from .const import (
    DOMAIN,
    TYPE_SMART_METER,
    ECHONET_INSTANT_POWER,
    ECHONET_CUMULATIVE_POWER,
    ECHONET_COEFFICIENT,
    ATTR_TEMPERATURE,
    ATTR_HUMIDITY,
    ATTR_ILLUMINANCE,
    ATTR_POWER,
    SUPPORT_FLAGS,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class NatureRemoSensorEntityDescription(SensorEntityDescription):
    """Class describing Nature Remo sensor entities."""

    value_fn: Callable[[Any], StateType] | None = None


SENSOR_TYPES: tuple[NatureRemoSensorEntityDescription, ...] = (
    # Power sensors
    NatureRemoSensorEntityDescription(
        key=ATTR_POWER,
        name="Power",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["smart_meter"]["echonetlite_properties"][ECHONET_INSTANT_POWER]["val"],
    ),
    NatureRemoSensorEntityDescription(
        key="energy",
        name="Energy",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: (
            data["smart_meter"]["echonetlite_properties"][ECHONET_CUMULATIVE_POWER]["val"]
            / ECHONET_COEFFICIENT
        ),
    ),
    # Environmental sensors
    NatureRemoSensorEntityDescription(
        key=ATTR_TEMPERATURE,
        name="Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: float(device["newest_events"]["te"]["val"]),
    ),
    NatureRemoSensorEntityDescription(
        key=ATTR_HUMIDITY,
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: float(device["newest_events"]["hu"]["val"]),
    ),
    NatureRemoSensorEntityDescription(
        key=ATTR_ILLUMINANCE,
        name="Illuminance",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: float(device["newest_events"]["il"]["val"]),
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
        if appliance["type"] == TYPE_SMART_METER:
            for description in SENSOR_TYPES[:2]:  # Power and Energy sensors
                if appliance["id"] in coordinator.data["appliances"]:
                    entities.append(
                        NatureRemoEnergySensor(coordinator, appliance, description)
                    )

    # Add environmental sensors
    for device in coordinator.data["devices"].values():
        device_model = device.get("firmware_version", "")
        supported_capabilities = SUPPORT_FLAGS.get(device_model, [])

        # Skip devices that are already handled as appliances
        if device["id"] in [
            app["device"]["id"] for app in coordinator.data["appliances"].values()
        ]:
            continue

        # Add temperature sensor if supported
        if "temperature" in supported_capabilities:
            entities.append(
                NatureRemoSensor(coordinator, device, SENSOR_TYPES[2])
            )

        # Add humidity sensor if supported
        if "humidity" in supported_capabilities:
            entities.append(
                NatureRemoSensor(coordinator, device, SENSOR_TYPES[3])
            )

        # Add illuminance sensor if supported
        if "illuminance" in supported_capabilities:
            entities.append(
                NatureRemoSensor(coordinator, device, SENSOR_TYPES[4])
            )

    async_add_entities(entities)


class NatureRemoSensor(NatureRemoDeviceBase, SensorEntity):
    """Implementation of a Nature Remo sensor."""

    entity_description: NatureRemoSensorEntityDescription

    def __init__(
        self,
        coordinator,
        device: dict[str, Any],
        description: NatureRemoSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device)
        self.entity_description = description
        self._attr_unique_id = f"{device['id']}_{description.key}"
        self._attr_name = f"{device.get('name', 'Nature Remo')} {description.name}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        try:
            if self.entity_description.value_fn:
                return self.entity_description.value_fn(self._device)
        except (KeyError, TypeError, ValueError) as err:
            _LOGGER.warning(
                "Error getting state for %s sensor %s: %s",
                self.entity_description.key,
                self.name,
                err,
            )
        return None


class NatureRemoEnergySensor(NatureRemoBase, SensorEntity):
    """Implementation of a Nature Remo energy sensor."""

    entity_description: NatureRemoSensorEntityDescription

    def __init__(
        self,
        coordinator,
        appliance: dict[str, Any],
        description: NatureRemoSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, appliance["device"]["id"])
        self.entity_description = description
        self._appliance = appliance
        self._attr_unique_id = f"{appliance['id']}_{description.key}"
        self._attr_name = f"{appliance['nickname']} {description.name}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        try:
            if self.entity_description.value_fn:
                appliance = self.coordinator.data["appliances"][self._appliance["id"]]
                return self.entity_description.value_fn(appliance)
        except (KeyError, TypeError, ValueError) as err:
            _LOGGER.warning(
                "Error getting state for %s sensor %s: %s",
                self.entity_description.key,
                self.name,
                err,
            )
        return None
