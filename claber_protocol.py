#!/usr/bin/env python3
"""
CLABER BLE PROTOCOL - COMPLETE AUTHENTICATION ALGORITHM
========================================================

DEVICE: Claber Dual myAquaSolar (cod. 8498)
BLE Service: 00FF2C23-2F17-198C-E343-3CA6FE3CEEBB
  Write:  02FF2C23-2F17-198C-E343-3CA6FE3CEEBB
  Notify: 01FF2C23-2F17-198C-E343-3CA6FE3CEEBB

PIN FORMAT:
  - 9 uppercase hex characters (0-9, A-F)
  - Characters [0:8]: data with Luhn mod-16 checksum (doubling odd positions from right)
  - Character [8]: 'D' = Dual/2-line model, 'E' = single-line model
  - Only first 8 chars used for BLE authentication
  - Only chars [1:8] (7 chars) are validated by the device

AUTHENTICATION PACKET:
  Format: [0x26][0x00][0x01][0x09][enc0][enc1][enc2..enc8][separator][checksum]
  Total: 15 bytes

  Where:
  - enc0: high nibble = seed_high (from key table), low nibble = random
  - enc1: high nibble = seed_low (from key table), low nibble = random
  - enc2..enc8: PIN[1:8] XOR key_stream (7 bytes, validated)
  - separator: determined by seed (from separator table)
  - checksum: (0x100 - sum(bytes[0:13])) & 0xFF

KEY DERIVATION:
  seed = (high_nibble(enc0) << 4) | high_nibble(enc1)  [8-bit, 256 possible values]
  key_stream = KEY_TABLE[seed]  [7 bytes]
  encrypted_pin = PIN_ascii[1:8] XOR key_stream

KNOWN KEY STREAMS (extracted from captured traffic):
  Seed 0x22: FC 96 AB 7B C0 D0 A3  (separator: 0xFA)
  Seed 0x67: 66 66 EA 58 4C 99 E7  (separator: 0xFB)
  Seed 0x98: E8 6A 5E 2E 4D 13 1C  (separator: 0xFC)
  Seed 0xDA: AB 29 06 87 34 FC 19  (separator: 0xFA)
  Seed 0xE6: 3A 69 C3 EE DB 2D 85  (separator: 0xFA)

COMMAND FORMAT (all commands):
  Write:    [0x26][type][sub][length][data...][0xFF][checksum]
  Response: [0x23][type][status][length][data...][separator][checksum]
  Checksum: (0x100 - sum(all bytes except separator and checksum)) & 0xFF

COMMANDS:
  Auth:        26 00 01 09 [9 encrypted bytes] [sep] [chk]
  Status:      26 01 00 00 FF [chk]
  Valve ctrl:  26 02 01 04 [L1_on] [L1_min] [L2_on] [L2_min] FF [chk]
  Programs:    26 04 01 0B [data...] FF [chk]
  Device info: 26 11 00 00 FF [chk]
  Energy:      26 23 00 00 FF [chk]

VALVE CONTROL:
  Line 1 ON 15min: 26 02 01 04 01 0F 00 00 FF C3
  Line 2 ON 15min: 26 02 01 04 00 00 01 0F FF C3
  ALL STOP:        26 02 01 04 00 00 00 00 FF D3

RESPONSE STATUS CODES:
  0x00 = Success
  0x01 = Wrong PIN / validation failed
  0x02 = Already authenticated / token reuse
  0x10 = Format error (wrong separator, bad structure)
  0x20 = Not authenticated (command requires auth first)

PROTOCOL FLOW:
  1. Connect to device
  2. Enable notifications on 01FF2C23-...
  3. Send auth packet (type 0x00)
  4. Wait for response status 0x00
  5. Send command(s)
  6. Auth must be re-sent before EACH command in a new connection
"""

import os

# Known key table entries (to be expanded via binary extraction or oracle testing)
KEY_TABLE = {
    0x22: bytes.fromhex('fc96ab7bc0d0a3'),
    0x67: bytes.fromhex('6666ea584c99e7'),
    0x98: bytes.fromhex('e86a5e2e4d131c'),
    0xDA: bytes.fromhex('ab29068734fc19'),
    0xE6: bytes.fromhex('3a69c3eedb2d85'),
}

SEP_TABLE = {
    0x22: 0xFA,
    0x67: 0xFB,
    0x98: 0xFC,
    0xDA: 0xFA,
    0xE6: 0xFA,
}

DEFAULT_SEED = 0xDA  # Most commonly used, separator 0xFA


def validate_pin(pin: str) -> bool:
    """Validate a Claber PIN format (9 hex chars, Luhn-16 on first 8, last = D/E)."""
    if len(pin) != 9:
        return False
    if not all(c in '0123456789ABCDEF' for c in pin.upper()):
        return False
    if pin[8].upper() not in ('D', 'E'):
        return False
    
    # Luhn mod 16 check (doubling odd positions from right) on first 8 chars
    digits = [int(c, 16) for c in pin[:8].upper()]
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 0:  # Double positions 1,3,5,7 from right
            d *= 2
            if d >= 16:
                d -= 15
        total += d
    return total % 16 == 0


def build_auth_packet(pin: str, seed: int = DEFAULT_SEED) -> bytes:
    """Build a BLE authentication packet for the given PIN.
    
    Args:
        pin: 8 or 9 char hex PIN (if 9, last char is ignored)
        seed: Key table seed (must be one of the known seeds)
    
    Returns:
        15-byte auth packet ready to write to the device
    """
    pin_upper = pin.upper()[:8]
    pin_ascii = pin_upper[1:8].encode('ascii')  # 7 bytes, chars [1:8]
    
    key_stream = KEY_TABLE[seed]
    separator = SEP_TABLE[seed]
    
    # Generate random low nibbles
    rand = os.urandom(2)
    enc0 = ((seed >> 4) << 4) | (rand[0] & 0x0F)
    enc1 = ((seed & 0x0F) << 4) | (rand[1] & 0x0F)
    
    # Encrypt PIN chars [1:8] with key stream
    enc_data = bytes(p ^ k for p, k in zip(pin_ascii, key_stream))
    
    # Assemble packet
    encrypted = bytes([enc0, enc1]) + enc_data  # 9 bytes
    header = bytes([0x26, 0x00, 0x01, 0x09])
    payload = header + encrypted
    checksum = (0x100 - (sum(payload) & 0xFF)) & 0xFF
    
    return payload + bytes([separator, checksum])


def build_command(cmd_type: int, sub: int, data: bytes = b'') -> bytes:
    """Build a generic command packet."""
    header = bytes([0x26, cmd_type, sub, len(data)])
    payload = header + data
    checksum = (0x100 - (sum(payload) & 0xFF)) & 0xFF
    return payload + bytes([0xFF, checksum])


MAX_IRRIGATION_MINUTES = 240  # 4 hours — hardware/app limit


def build_valve_command(line1_on: bool = False, line1_minutes: int = 0,
                        line2_on: bool = False, line2_minutes: int = 0) -> bytes:
    """Build a raw valve control command (low-level)."""
    data = bytes([
        0x01 if line1_on else 0x00,
        line1_minutes & 0xFF,
        0x01 if line2_on else 0x00,
        line2_minutes & 0xFF,
    ])
    return build_command(0x02, 0x01, data)


def turn_on_line(line: int, minutes: int) -> bytes:
    """Build command to turn on a valve line.

    Args:
        line: Line number (1 or 2). Only one line can be active at a time.
        minutes: Irrigation duration in minutes (1–240). Maximum 4 hours.

    Returns:
        Command bytes ready to send after authentication.

    Raises:
        ValueError: If line is not 1 or 2, or duration out of range.
    """
    if line not in (1, 2):
        raise ValueError(f"Invalid line {line}: must be 1 or 2")
    if minutes < 1 or minutes > MAX_IRRIGATION_MINUTES:
        raise ValueError(f"Duration {minutes}min out of range (1–{MAX_IRRIGATION_MINUTES})")
    if line == 1:
        return build_valve_command(line1_on=True, line1_minutes=minutes)
    else:
        return build_valve_command(line2_on=True, line2_minutes=minutes)


def turn_off_line(line: int) -> bytes:
    """Build command to turn off a specific valve line (stops all).

    Note: The protocol only supports a "stop all" command — there is no
    per-line stop. This sends stop-all regardless of which line is specified.

    Args:
        line: Line number (1 or 2).

    Returns:
        Command bytes (stop all valves).
    """
    if line not in (1, 2):
        raise ValueError(f"Invalid line {line}: must be 1 or 2")
    return build_valve_command()


def stop_all() -> bytes:
    """Build command to stop all irrigation."""
    return build_valve_command()


# Command constants
CMD_STATUS = build_command(0x01, 0x00)
CMD_ENERGY = build_command(0x23, 0x00)
CMD_DEVICE_INFO = build_command(0x11, 0x00)
CMD_STOP_ALL = build_valve_command()


# --- Broadcast advertisement decoding ---

# Solar irradiance thresholds (confirmed empirically):
#   0 = None, 5-49 = Sufficient, 50-149 = Good, >=150 = Excellent
#   Boundary confirmations: 4→None, 5→Sufficient, 6→Sufficient, 49→Sufficient, 50→Good, 137→Good, 150→Excellent
SOLAR_THRESHOLDS = [(150, "Excellent"), (50, "Good"), (5, "Sufficient"), (1, "Poor")]

# Battery/energy thresholds (from status byte lower 5 bits):
#   >=0x0D = Excellent, 0x0B-0x0C = Good, 0x08-0x0A = Sufficient,
#   0x05-0x07 = Energy Saving, 0x01-0x04 = Insufficient
BATTERY_THRESHOLDS = [(0x0D, "Excellent"), (0x0B, "Good"), (0x08, "Sufficient"),
                      (0x05, "Energy Saving"), (0x01, "Insufficient")]


def decode_broadcast(company_id: int, data: bytes) -> dict:
    """Decode a Claber BLE manufacturer-specific advertisement.

    Args:
        company_id: 16-bit "company ID" from BLE advertisement (LE16).
        data: Remaining manufacturer data bytes (at least 7 bytes).

    Returns:
        Dictionary with decoded fields:
          solar_irradiance (int), solar_label (str),
          energy_level (int), battery_label (str),
          line1_active (bool), line1_remaining (int),
          line2_active (bool), line2_remaining (int),
          flags (int)
    """
    solar_irradiance = (company_id >> 8) & 0xFF
    status_byte = data[0]
    l1_remaining = data[1]
    l2_remaining = data[2]
    flags = data[3]

    energy_level = status_byte & 0x1F
    l1_active = bool(status_byte & 0x20)
    l2_active = bool(status_byte & 0x80)

    solar_label = "None"
    for threshold, label in SOLAR_THRESHOLDS:
        if solar_irradiance >= threshold:
            solar_label = label
            break

    battery_label = "Data Unavailable"
    for threshold, label in BATTERY_THRESHOLDS:
        if energy_level >= threshold:
            battery_label = label
            break

    return {
        "solar_irradiance": solar_irradiance,
        "solar_label": solar_label,
        "energy_level": energy_level,
        "battery_label": battery_label,
        "line1_active": l1_active,
        "line1_remaining": l1_remaining,
        "line2_active": l2_active,
        "line2_remaining": l2_remaining,
        "flags": flags,
    }

