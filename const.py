"""Constants for Nature Remo integration."""
from datetime import timedelta

# Domain
DOMAIN = "nature_remo"

# Configuration
CONF_ACCESS_TOKEN = "access_token"
CONF_COOL_TEMP = "cool_temperature"
CONF_HEAT_TEMP = "heat_temperature"

# Device Types
TYPE_AC = "AC"
TYPE_TV = "TV"
TYPE_LIGHT = "LIGHT"
TYPE_IR = "IR"
TYPE_SMART_METER = "EL_SMART_METER"

# API Constants
API_ENDPOINT = "https://api.nature.global/1/"
API_DEVICES = "devices"
API_APPLIANCES = "appliances"

# Defaults
DEFAULT_UPDATE_INTERVAL = timedelta(seconds=60)
DEFAULT_COOL_TEMP = 28
DEFAULT_HEAT_TEMP = 20
DEFAULT_TIMEOUT = 30  # seconds

# AC Operation Modes
MODE_MAP = {
    "auto": "auto",
    "cool": "cool",
    "warm": "warm",
    "dry": "dry",
    "blow": "blow",
    "off": "power-off"
}

# Energy Monitoring (For Nature Remo E/E lite)
ECHONET_INSTANT_POWER = 231  # Measured instantaneous power consumption
ECHONET_CUMULATIVE_POWER = 224  # Measured cumulative power consumption
ECHONET_COEFFICIENT = 1000  # Coefficient for kWh conversion

# Device Information
MANUFACTURER = "Nature"
MODEL_REMO = "Remo"
MODEL_REMO_2 = "Remo 2"
MODEL_REMO_E = "Remo E"
MODEL_REMO_E_LITE = "Remo E lite"
MODEL_REMO_MINI = "Remo mini"

# Update Intervals
UPDATE_INTERVAL_SENSORS = timedelta(seconds=60)
UPDATE_INTERVAL_CLIMATE = timedelta(seconds=60)
UPDATE_INTERVAL_ENERGY = timedelta(seconds=30)

# Event Names
EVENT_DEVICE_UPDATE = f"{DOMAIN}_device_update"
EVENT_APPLIANCE_UPDATE = f"{DOMAIN}_appliance_update"

# Error Messages
ERROR_AUTH = "Invalid access token"
ERROR_TIMEOUT = "Request timed out"
ERROR_CONNECTION = "Connection error"
ERROR_RESPONSE = "Invalid response from API"

# Supported Device Capabilities
SUPPORT_FLAGS = {
    MODEL_REMO: ["temperature", "humidity", "illuminance"],
    MODEL_REMO_2: ["temperature", "humidity", "illuminance"],
    MODEL_REMO_E: ["temperature", "humidity", "illuminance", "power"],
    MODEL_REMO_E_LITE: ["power"],
    MODEL_REMO_MINI: ["temperature"]
}

# State Attributes
ATTR_TEMPERATURE = "temperature"
ATTR_HUMIDITY = "humidity"
ATTR_ILLUMINANCE = "illuminance"
ATTR_POWER = "power"
ATTR_OPERATION_MODE = "operation_mode"
ATTR_TARGET_TEMPERATURE = "target_temperature"
ATTR_FAN_MODE = "fan_mode"
ATTR_SWING_MODE = "swing_mode"
ATTR_LAST_UPDATE = "last_update"
