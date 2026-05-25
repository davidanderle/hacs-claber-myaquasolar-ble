#!/usr/bin/env python3
"""Tests for claber_protocol module."""

from claber_protocol import (
    build_auth_packet, build_command, build_valve_command,
    decode_broadcast, validate_pin,
    CMD_STATUS, CMD_ENERGY, CMD_DEVICE_INFO, CMD_STOP_ALL,
)


def test_pin_validation():
    assert validate_pin("00000000D") is True
    assert validate_pin("00000000E") is True   # E suffix also valid
    assert validate_pin("10000000D") is False  # fails Luhn-16
    assert validate_pin("SHORT") is False
    assert validate_pin("00000000X") is False  # invalid suffix


def test_auth_packet_length():
    pkt = build_auth_packet("00000000D")
    assert len(pkt) == 15
    assert pkt[0] == 0x26
    assert pkt[1:4] == b'\x00\x01\x09'


def test_auth_packet_seed_encoding():
    pkt = build_auth_packet("00000000D", seed=0xDA)
    assert (pkt[4] >> 4) == 0xD
    assert (pkt[5] >> 4) == 0xA


def test_command_constants():
    assert CMD_STATUS == bytes.fromhex('26010000ffd9')
    assert CMD_ENERGY == bytes.fromhex('26230000ffb7')
    assert CMD_DEVICE_INFO == bytes.fromhex('26110000ffc9')
    assert CMD_STOP_ALL == bytes.fromhex('2602010400000000ffd3')


def test_valve_command():
    assert build_valve_command(line1_on=True, line1_minutes=15) == bytes.fromhex('26020104010f0000ffc3')
    assert build_valve_command(line2_on=True, line2_minutes=30) == bytes.fromhex('260201040000011effb4')


def test_decode_broadcast_solar():
    # Excellent: solar=150
    r = decode_broadcast(0x9642, bytes.fromhex('0D0000810174D1'))
    assert r["solar_label"] == "Excellent"
    assert r["solar_irradiance"] == 150

    # Good: solar=137
    r = decode_broadcast(0x8942, bytes.fromhex('0D0000810174D1'))
    assert r["solar_label"] == "Good"
    assert r["solar_irradiance"] == 137

    # Good: solar=50 (boundary)
    r = decode_broadcast(0x3242, bytes.fromhex('0D0000810174D1'))
    assert r["solar_label"] == "Good"

    # Sufficient: solar=49
    r = decode_broadcast(0x3142, bytes.fromhex('0D0000810174D1'))
    assert r["solar_label"] == "Sufficient"

    # Sufficient: solar=5 (boundary)
    r = decode_broadcast(0x0542, bytes.fromhex('0D0000810174D1'))
    assert r["solar_label"] == "Sufficient"

    # Poor: solar=4
    r = decode_broadcast(0x0442, bytes.fromhex('0D0000810174D1'))
    assert r["solar_label"] == "Poor"


def test_decode_broadcast_battery():
    # Excellent: energy=0x0D
    r = decode_broadcast(0xFA42, bytes.fromhex('0D0000810174D1'))
    assert r["battery_label"] == "Excellent"

    # Good: energy=0x0B
    r = decode_broadcast(0xFA42, bytes.fromhex('0B0000810174D1'))
    assert r["battery_label"] == "Good"

    # Insufficient: energy=0x03
    r = decode_broadcast(0xFA42, bytes.fromhex('030000810174D1'))
    assert r["battery_label"] == "Insufficient"


def test_decode_broadcast_watering():
    # Line 1 active, 12 min remaining
    r = decode_broadcast(0xFA42, bytes.fromhex('2D0C00810174D1'))
    assert r["line1_active"] is True
    assert r["line1_remaining"] == 12
    assert r["line2_active"] is False

    # Line 2 active, 5 min remaining
    r = decode_broadcast(0xFA42, bytes.fromhex('8D0005810174D1'))
    assert r["line2_active"] is True
    assert r["line2_remaining"] == 5


if __name__ == "__main__":
    test_pin_validation()
    test_auth_packet_length()
    test_auth_packet_seed_encoding()
    test_command_constants()
    test_valve_command()
    test_decode_broadcast_solar()
    test_decode_broadcast_battery()
    test_decode_broadcast_watering()
    print("✓ All tests passed!")
