#!/usr/bin/env python3
"""Demo: Authenticate and cycle valves - Line 1 ON 10s, OFF, Line 2 ON 10s, OFF.

Protocol pattern (from HCI capture): connect → auth → command → disconnect.
Each command uses a fresh connection.
"""

import asyncio
import sys
from bleak import BleakClient, BleakScanner
from claber_protocol import build_auth_packet, build_valve_command

NOTIFY_UUID = "01ff2c23-2f17-198c-e343-3ca6fe3ceebb"
WRITE_UUID = "02ff2c23-2f17-198c-e343-3ca6fe3ceebb"

if len(sys.argv) < 2:
    raise SystemExit("Usage: python valve_demo.py <PIN>")
PIN = sys.argv[1]

responses = []


def notification_handler(sender, data: bytearray):
    responses.append(bytes(data))


async def find_device():
    device = None

    def cb(d, adv):
        nonlocal device
        if d.name and "claber" in d.name.lower():
            device = d

    scanner = BleakScanner(detection_callback=cb)
    await scanner.start()
    for _ in range(120):
        await asyncio.sleep(0.5)
        if device:
            break
    await scanner.stop()
    return device


async def send_command(device, cmd, label="CMD"):
    """Connect, authenticate, send one command, disconnect."""
    global responses
    client = BleakClient(device, timeout=30.0)
    try:
        await client.connect()
        await client.start_notify(NOTIFY_UUID, notification_handler)
        await asyncio.sleep(0.3)

        # Authenticate
        responses = []
        await client.write_gatt_char(WRITE_UUID, build_auth_packet(PIN))
        await asyncio.sleep(0.5)
        if not responses or responses[0][2] != 0x00:
            status = responses[0][2] if responses else -1
            print(f"  ✗ AUTH failed: status=0x{status:02X}")
            return False

        # Send command
        responses = []
        await client.write_gatt_char(WRITE_UUID, cmd)
        await asyncio.sleep(0.5)
        if responses:
            status = responses[0][2] if len(responses[0]) > 2 else -1
            ok = "✓" if status == 0x00 else "✗"
            print(f"  {ok} {label}: status=0x{status:02X}")
            return status == 0x00
        print(f"  ✗ {label}: NO RESPONSE")
        return False

    finally:
        if client.is_connected:
            await client.disconnect()
        await asyncio.sleep(1.5)  # Let device settle (matches app's ~1.5s post-disconnect gap)


async def main():
    print("Scanning for Claber device...")
    device = await find_device()
    if not device:
        print("Device not found!")
        return

    print(f"Found: {device.name}\n")

    # --- Line 1 ON ---
    print("[1] Line 1 ON...")
    if not await send_command(device, build_valve_command(line1_on=True, line1_minutes=1), "LINE1 ON"):
        return

    print("    Waiting 10 seconds...")
    await asyncio.sleep(10)

    # --- Line 1 OFF ---
    print("[2] Line 1 OFF...")
    if not await send_command(device, build_valve_command(), "STOP ALL"):
        return

    print("    Waiting 5 seconds...")
    await asyncio.sleep(5)

    # --- Line 2 ON ---
    print("[3] Line 2 ON...")
    if not await send_command(device, build_valve_command(line2_on=True, line2_minutes=1), "LINE2 ON"):
        return

    print("    Waiting 10 seconds...")
    await asyncio.sleep(10)

    # --- Line 2 OFF ---
    print("[4] Line 2 OFF...")
    if not await send_command(device, build_valve_command(), "STOP ALL"):
        return

    print("\n✓ Demo complete!")


if __name__ == "__main__":
    asyncio.run(main())
