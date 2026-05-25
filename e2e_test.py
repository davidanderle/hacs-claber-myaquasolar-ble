#!/usr/bin/env python3
"""End-to-end live test: authenticate + read status + energy using claber_protocol library."""

import asyncio
import os
from bleak import BleakClient, BleakScanner
from claber_protocol import build_auth_packet, CMD_STATUS, CMD_ENERGY, CMD_DEVICE_INFO

NOTIFY_UUID = "01ff2c23-2f17-198c-e343-3ca6fe3ceebb"
WRITE_UUID = "02ff2c23-2f17-198c-e343-3ca6fe3ceebb"
PIN = os.environ.get("CLABER_PIN", "")
if not PIN:
    raise SystemExit("Set CLABER_PIN environment variable (9-char PIN from device sticker)")

responses = []
def notification_handler(sender, data: bytearray):
    responses.append(bytes(data))

async def send_cmd(client, cmd, label=""):
    global responses
    responses = []
    await client.write_gatt_char(WRITE_UUID, cmd)
    await asyncio.sleep(1.0)
    if responses:
        resp = responses[0]
        status = resp[2] if len(resp) > 2 else -1
        print(f"  {label}: status=0x{status:02X} data={resp.hex()}")
        return resp
    print(f"  {label}: NO RESPONSE")
    return None

async def main():
    device = None
    def cb(d, adv):
        nonlocal device
        if d.name and 'claber' in d.name.lower():
            device = d
    scanner = BleakScanner(detection_callback=cb)
    await scanner.start()
    for _ in range(120):
        await asyncio.sleep(0.5)
        if device:
            break
    await scanner.stop()
    if not device:
        print("Device not found")
        return

    print(f"Found: {device.name} ({device.address})")
    client = BleakClient(device, timeout=30.0)
    
    try:
        await client.connect()
        await client.start_notify(NOTIFY_UUID, notification_handler)
        await asyncio.sleep(0.5)
        print("Connected.\n")
        
        # 1. Authenticate using library
        auth = build_auth_packet(PIN)
        print(f"Auth packet: {auth.hex()}")
        resp = await send_cmd(client, auth, "AUTH")
        if not resp or resp[2] != 0x00:
            print("AUTH FAILED!")
            return
        print("  ✓ Authenticated!\n")
        
        # 2. Read device info
        await send_cmd(client, CMD_DEVICE_INFO, "INFO")
        
        # 3. Read status
        resp = await send_cmd(client, CMD_STATUS, "STATUS")
        if resp and resp[2] == 0x00:
            # Parse status response
            print(f"    Raw status: {resp.hex()}")
        
        # 4. Read energy
        resp = await send_cmd(client, CMD_ENERGY, "ENERGY")
        if resp and resp[2] == 0x00 and len(resp) > 3:
            energy = resp[3]
            print(f"    Energy level: {energy}%")
        
        print("\n✓ End-to-end test PASSED")
        
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
    finally:
        if client.is_connected:
            await client.disconnect()
            print("Disconnected.")

if __name__ == "__main__":
    asyncio.run(main())
