"""Claber BLE protocol helpers."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass

from bleak import BleakClient
from bleak.exc import BleakError
from bleak_retry_connector import establish_connection
from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

from .const import (
    BATTERY_THRESHOLDS,
    DEFAULT_SEED,
    KEY_TABLE,
    MAX_IRRIGATION_MINUTES,
    NOTIFY_CHAR_UUID,
    RSSI_THRESHOLDS,
    SEP_TABLE,
    SOLAR_THRESHOLDS,
    STATUS_SUCCESS,
    WRITE_CHAR_UUID,
)


@dataclass(slots=True, frozen=True)
class ClaberBroadcastData:
    """Decoded manufacturer advertisement payload."""

    solar_irradiance: int
    solar_label: str
    energy_level: int
    battery_percent: int
    battery_label: str
    line1_active: bool
    line1_remaining: int
    line2_active: bool
    line2_remaining: int
    rain_detected: bool
    is_watering: bool
    flags: int
    rssi: int | None
    rssi_label: str


@dataclass(slots=True, frozen=True)
class ClaberCommandResult:
    """Result of one auth + command session."""

    auth_response: bytes | None
    command_response: bytes | None
    auth_status: int | None
    command_status: int | None

    @property
    def ok(self) -> bool:
        """Return True when auth and command statuses are both success."""
        return self.auth_status == STATUS_SUCCESS and self.command_status == STATUS_SUCCESS


def validate_pin(pin: str) -> bool:
    """Validate a Claber PIN format (9 hex chars, Luhn-16 on first 8, last = D/E)."""
    pin_upper = pin.strip().upper()
    if len(pin_upper) != 9:
        return False
    if not all(char in "0123456789ABCDEF" for char in pin_upper):
        return False
    if pin_upper[8] not in ("D", "E"):
        return False

    digits = [int(char, 16) for char in pin_upper[:8]]
    total = 0
    for index, digit in enumerate(reversed(digits)):
        if index % 2 == 0:
            digit *= 2
            if digit >= 16:
                digit -= 15
        total += digit
    return total % 16 == 0


def build_auth_packet(pin: str, seed: int = DEFAULT_SEED) -> bytes:
    """Build a BLE authentication packet for a PIN."""
    if seed not in KEY_TABLE:
        raise ValueError(f"Unknown seed 0x{seed:02X}")

    pin_upper = pin.strip().upper()
    if len(pin_upper) < 8:
        raise ValueError("PIN must contain at least 8 hex characters")

    pin_ascii = pin_upper[:8][1:8].encode("ascii")
    key_stream = KEY_TABLE[seed]
    separator = SEP_TABLE[seed]

    random_bytes = os.urandom(2)
    enc0 = ((seed >> 4) << 4) | (random_bytes[0] & 0x0F)
    enc1 = ((seed & 0x0F) << 4) | (random_bytes[1] & 0x0F)
    enc_data = bytes(pin_char ^ key for pin_char, key in zip(pin_ascii, key_stream, strict=True))

    encrypted = bytes([enc0, enc1]) + enc_data
    header = bytes([0x26, 0x00, 0x01, 0x09])
    payload = header + encrypted
    checksum = (0x100 - (sum(payload) & 0xFF)) & 0xFF

    return payload + bytes([separator, checksum])


def build_command(cmd_type: int, sub_type: int, data: bytes = b"") -> bytes:
    """Build a generic Claber command packet."""
    header = bytes([0x26, cmd_type, sub_type, len(data)])
    payload = header + data
    checksum = (0x100 - (sum(payload) & 0xFF)) & 0xFF
    return payload + bytes([0xFF, checksum])


def build_valve_command(
    line1_on: bool = False,
    line1_minutes: int = 0,
    line2_on: bool = False,
    line2_minutes: int = 0,
) -> bytes:
    """Build a raw valve control packet."""
    data = bytes(
        [
            0x01 if line1_on else 0x00,
            line1_minutes & 0xFF,
            0x01 if line2_on else 0x00,
            line2_minutes & 0xFF,
        ]
    )
    return build_command(0x02, 0x01, data)


def turn_on_line(line: int, minutes: int) -> bytes:
    """Build command to turn on a single valve line."""
    if line not in (1, 2):
        raise ValueError("line must be 1 or 2")
    if not 1 <= minutes <= MAX_IRRIGATION_MINUTES:
        raise ValueError(f"minutes must be between 1 and {MAX_IRRIGATION_MINUTES}")

    if line == 1:
        return build_valve_command(line1_on=True, line1_minutes=minutes)
    return build_valve_command(line2_on=True, line2_minutes=minutes)


def stop_all() -> bytes:
    """Build command to stop all valves."""
    return build_valve_command()


CMD_STATUS = build_command(0x01, 0x00)
CMD_ENERGY = build_command(0x23, 0x00)
CMD_DEVICE_INFO = build_command(0x11, 0x00)
CMD_STOP_ALL = stop_all()


def _extract_status(response: bytes | None) -> int | None:
    """Extract the protocol status byte from a response frame."""
    if response is None or len(response) < 3:
        return None
    return response[2]


def decode_solar_label(irradiance: int) -> str:
    """Map raw solar irradiance to a level label."""
    for threshold, label in SOLAR_THRESHOLDS:
        if irradiance >= threshold:
            return label
    return "None"


def decode_battery_label(level: int) -> str:
    """Map raw battery level to label."""
    for threshold, label in BATTERY_THRESHOLDS:
        if level >= threshold:
            return label
    return "Data Unavailable"


def decode_rssi_label(rssi: int | None) -> str:
    """Map RSSI dBm to a compact quality label."""
    if rssi is None:
        return "No signal"

    for threshold, label in RSSI_THRESHOLDS:
        if rssi >= threshold:
            return label
    return "No signal"


def decode_broadcast(company_id: int, data: bytes, rssi: int | None) -> ClaberBroadcastData:
    """Decode Claber manufacturer data into a strongly typed payload."""
    solar_irradiance = (company_id >> 8) & 0xFF
    status_byte = data[0]
    line1_remaining = data[1]
    line2_remaining = data[2]
    flags = data[3]

    energy_level = status_byte & 0x1F
    battery_percent = round((energy_level / 31) * 100)

    line1_active = bool(status_byte & 0x20)
    line2_active = bool(status_byte & 0x80)
    rain_detected = (flags & 0x01) == 0

    return ClaberBroadcastData(
        solar_irradiance=solar_irradiance,
        solar_label=decode_solar_label(solar_irradiance),
        energy_level=energy_level,
        battery_percent=battery_percent,
        battery_label=decode_battery_label(energy_level),
        line1_active=line1_active,
        line1_remaining=line1_remaining,
        line2_active=line2_active,
        line2_remaining=line2_remaining,
        rain_detected=rain_detected,
        is_watering=line1_active or line2_active,
        flags=flags,
        rssi=rssi,
        rssi_label=decode_rssi_label(rssi),
    )


def parse_broadcast(
    manufacturer_data: Mapping[int, bytes],
    rssi: int | None,
) -> ClaberBroadcastData | None:
    """Parse the first valid manufacturer data section from an advertisement."""
    for company_id, payload in manufacturer_data.items():
        data = bytes(payload)
        if len(data) < 7:
            continue
        return decode_broadcast(company_id, data, rssi)
    return None


async def _write_and_wait_response(
    client: BleakClient,
    notification_queue: asyncio.Queue[bytes],
    payload: bytes,
    timeout: float,
) -> bytes | None:
    """Write one packet and wait for the next notification frame."""
    while not notification_queue.empty():
        with suppress(asyncio.QueueEmpty):
            notification_queue.get_nowait()

    await client.write_gatt_char(WRITE_CHAR_UUID, payload, response=False)

    try:
        return await asyncio.wait_for(notification_queue.get(), timeout=timeout)
    except TimeoutError:
        return None


async def authenticate_and_send(
    hass: HomeAssistant,
    address: str,
    pin: str,
    command: bytes,
    timeout: float = 4.0,
) -> ClaberCommandResult:
    """Open a BLE session, authenticate, send one command, and return responses."""
    ble_device = bluetooth.async_ble_device_from_address(hass, address.upper(), connectable=True)
    if ble_device is None:
        raise BleakError(f"No connectable BLE device available for address {address}")

    client = await establish_connection(
        BleakClient,
        ble_device,
        f"claber-{address}",
    )

    notification_queue: asyncio.Queue[bytes] = asyncio.Queue()

    def _notification_handler(_sender: int, data: bytearray) -> None:
        notification_queue.put_nowait(bytes(data))

    try:
        await client.start_notify(NOTIFY_CHAR_UUID, _notification_handler)

        auth_response = await _write_and_wait_response(
            client,
            notification_queue,
            build_auth_packet(pin),
            timeout,
        )
        auth_status = _extract_status(auth_response)
        if auth_status != STATUS_SUCCESS:
            return ClaberCommandResult(
                auth_response=auth_response,
                command_response=None,
                auth_status=auth_status,
                command_status=None,
            )

        command_response = await _write_and_wait_response(
            client,
            notification_queue,
            command,
            timeout,
        )
        command_status = _extract_status(command_response)

        return ClaberCommandResult(
            auth_response=auth_response,
            command_response=command_response,
            auth_status=auth_status,
            command_status=command_status,
        )
    finally:
        with suppress(Exception):
            await client.stop_notify(NOTIFY_CHAR_UUID)
        with suppress(Exception):
            await client.disconnect()
