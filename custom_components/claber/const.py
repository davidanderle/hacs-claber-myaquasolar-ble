"""Constants for the Claber myAquaSolar integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "claber"

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SWITCH,
]

CONF_ADDRESS = "address"
CONF_PIN = "pin"

SERVICE_UUID = "00ff2c23-2f17-198c-e343-3ca6fe3ceebb"
NOTIFY_CHAR_UUID = "01ff2c23-2f17-198c-e343-3ca6fe3ceebb"
WRITE_CHAR_UUID = "02ff2c23-2f17-198c-e343-3ca6fe3ceebb"

DEFAULT_SEED = 0xDA
DEFAULT_DURATION_MINUTES = 15
MAX_IRRIGATION_MINUTES = 240

STATUS_SUCCESS = 0x00

KEY_TABLE = {
    0x22: bytes.fromhex("fc96ab7bc0d0a3"),
    0x67: bytes.fromhex("6666ea584c99e7"),
    0x98: bytes.fromhex("e86a5e2e4d131c"),
    0xDA: bytes.fromhex("ab29068734fc19"),
    0xE6: bytes.fromhex("3a69c3eedb2d85"),
}

SEP_TABLE = {
    0x22: 0xFA,
    0x67: 0xFB,
    0x98: 0xFC,
    0xDA: 0xFA,
    0xE6: 0xFA,
}

SOLAR_THRESHOLDS = [
    (150, "Excellent"),
    (50, "Good"),
    (5, "Sufficient"),
    (1, "Poor"),
]

BATTERY_THRESHOLDS = [
    (0x0D, "Excellent"),
    (0x0B, "Good"),
    (0x08, "Sufficient"),
    (0x05, "Energy Saving"),
    (0x01, "Insufficient"),
]

RSSI_THRESHOLDS = [
    (-60, "Excellent"),
    (-70, "Good"),
    (-80, "Fair"),
    (-95, "Weak"),
]

SOLAR_LEVEL_OPTIONS = [
    "Excellent",
    "Good",
    "Sufficient",
    "Poor",
    "None",
]

RSSI_LEVEL_OPTIONS = [
    "Excellent",
    "Good",
    "Fair",
    "Weak",
    "No signal",
]
