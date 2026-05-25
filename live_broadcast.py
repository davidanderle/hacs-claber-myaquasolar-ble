#!/usr/bin/env python3
"""Live broadcast decoder for Claber myAquaSolar BLE advertisements."""

import asyncio
from bleak import BleakScanner


def decode_rssi(rssi):
    """Map RSSI dBm to signal quality label."""
    if rssi >= -50:
        return "Excellent"
    elif rssi >= -60:
        return "Good"
    elif rssi >= -70:
        return "Moderate"
    elif rssi >= -80:
        return "Sufficient"
    elif rssi >= -90:
        return "Poor"
    else:
        return "None"


def decode_battery(level):
    """Decode energy level from status byte lower bits."""
    if level >= 0x0D:
        return "Excellent"
    elif level >= 0x0B:
        return "Good"
    elif level >= 0x08:
        return "Sufficient"
    elif level >= 0x05:
        return "Energy Saving"
    elif level >= 0x01:
        return "Insufficient"
    else:
        return "Data Unavailable"


def decode_solar(irradiance):
    """Decode solar irradiance from company ID high byte (0-255).
    Confirmed: 5=Poor, 48,49=Sufficient, 50,62,125=Good, 207,250=Excellent.
    Thresholds: 8, 50, 128.
    """
    if irradiance >= 128:
        return "Excellent"
    elif irradiance >= 50:
        return "Good"
    elif irradiance >= 8:
        return "Sufficient"
    elif irradiance >= 1:
        return "Poor"
    else:
        return "None"


def decode_broadcast(rssi, company_id, data):
    """Decode a full broadcast into human-readable fields."""
    solar_irradiance = (company_id >> 8) & 0xFF
    status_byte = data[0]
    l1_remaining = data[1]
    l2_remaining = data[2]
    flags = data[3]

    # Battery/energy level = status byte with watering bits masked out
    energy_level = status_byte & 0x1F

    # Watering flags
    l1_active = bool(status_byte & 0x20)
    l2_active = bool(status_byte & 0x80)
    watering = "Watering" if (l1_active or l2_active) else "Not watering"

    # Rain status from flags byte
    # 0x81 = 1000 0001 — hypothesis: bit 0 = no rain sensor or not raining
    rain = "Raining" if (flags & 0x01) == 0 else "Not raining"

    rssi_label = decode_rssi(rssi)
    battery_label = decode_battery(energy_level)
    solar_label = decode_solar(solar_irradiance)

    # Raw hex: company_id (2 bytes) + data (7 bytes) = 9 bytes total
    raw = f"{company_id:04X}{data.hex().upper()}"

    line = (
        f"RSSI: {rssi_label} ({rssi}dBm), "
        f"Battery: {battery_label} (0x{energy_level:02X}), "
        f"Solar Irradiance: {solar_label} ({solar_irradiance}), "
        f"Rain status: {rain}, "
        f"Watering status: {watering}"
    )

    if l1_active:
        line += f" [L1:{l1_remaining}min]"
    if l2_active:
        line += f" [L2:{l2_remaining}min]"

    line += f"  {{0x{raw}}}"
    return line


async def main():
    print("Claber myAquaSolar — Live Broadcast Decoder")
    print("=" * 80)
    print("Listening for advertisements... (Ctrl+C to stop)\n")

    last_raw = None

    def cb(device, adv_data):
        nonlocal last_raw
        if not device.name or "claber" not in device.name.lower():
            return

        for company_id, data in adv_data.manufacturer_data.items():
            data = bytes(data)
            if len(data) < 7:
                continue

            # Only print if data changed
            raw_key = (company_id >> 8, data.hex())
            if raw_key == last_raw:
                continue
            last_raw = raw_key

            line = decode_broadcast(adv_data.rssi, company_id, data)
            print(line)

    scanner = BleakScanner(detection_callback=cb)
    await scanner.start()

    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        await scanner.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
