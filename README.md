# Claber myAquaSolar BLE Protocol — Reverse Engineering

Fully reverse-engineered BLE protocol for the **[Claber Dual myAquaSolar](https://www.easygardenirrigation.co.uk/products/claber-dual-myaquasolar-8498)** (cod. 8498) — a 2-channel solar-powered outdoor irrigation valve. No public documentation or HACS integration existed prior to this work.

---

## Device

| Property | Detail |
|---|---|
| Model | Claber Dual myAquaSolar (cod. 8498) |
| Channels | 2 solenoid outputs (mutually exclusive — only one active at a time) |
| Power | Solar panel + rechargeable battery |
| Protocol | Bluetooth Low Energy (proprietary, single GATT service) |
| Official app | myClaber (`com.claber.myaquasolar`, Flutter + native Dart AOT) |
| BLE name | `Claber Sun-XXXXX` (suffix derived from MAC) |

---

## BLE GATT

Single service with two characteristics:

| UUID | Role |
|------|------|
| `00FF2C23-2F17-198C-E343-3CA6FE3CEEBB` | Service |
| `02FF2C23-2F17-198C-E343-3CA6FE3CEEBB` | Write (write / write-without-response) |
| `01FF2C23-2F17-198C-E343-3CA6FE3CEEBB` | Notify (responses) |

---

## Connection Pattern

The device uses **atomic sessions**:

```
connect → authenticate → ONE command → disconnect
```

- Each command requires a fresh BLE connection and re-authentication
- The device drops idle connections after ~5–8 seconds
- Sending a second auth on the same connection returns status 0x10 (format error)

---

## PIN Format

The 9-character PIN printed on the device sticker:

```
XXXXXXXXD
├──────┤│
│       └── Character [8]: Model type (D=Dual/2-line, E=single-line)
└────────── Characters [0:8]: Luhn mod-16 validated (doubling odd positions from right)
```

- Only characters `[1:8]` (7 chars) are transmitted over BLE
- Character `[0]` is a check digit, never sent

---

## Authentication

**Packet structure** (15 bytes):

```
26 00 01 09 [enc0] [enc1] [enc2..enc8] [separator] [checksum]
─────────── ──────────────────────────── ────────── ──────────
 header (4)     encrypted data (9)         sep (1)   chk (1)
```

**Algorithm:**

1. Choose a `seed` from the known key table (8-bit value)
2. Generate two random low nibbles (`r0`, `r1`)
3. `enc0 = (seed >> 4) << 4 | r0` — high nibble encodes seed upper half
4. `enc1 = (seed & 0x0F) << 4 | r1` — high nibble encodes seed lower half
5. `enc2..enc8 = PIN_ascii[1:8] XOR key_stream[seed]` — 7 bytes
6. `separator = SEP_TABLE[seed]`
7. `checksum = (0x100 - sum(header + encrypted)) & 0xFF`

**Known key streams** (universal — not device-specific):

| Seed | Key Stream | Separator |
|------|-----------|-----------|
| `0x22` | `FC 96 AB 7B C0 D0 A3` | `0xFA` |
| `0x67` | `66 66 EA 58 4C 99 E7` | `0xFB` |
| `0x98` | `E8 6A 5E 2E 4D 13 1C` | `0xFC` |
| `0xDA` | `AB 29 06 87 34 FC 19` | `0xFA` |
| `0xE6` | `3A 69 C3 EE DB 2D 85` | `0xFA` |

The full table has 256 entries. Only one known seed is needed for full device control.

---

## Commands

All commands follow: `26 [type] [sub] [length] [data...] FF [checksum]`

Checksum: `(0x100 - sum(all bytes except FF and checksum)) & 0xFF`

| Command | Hex Packet | Notes |
|---------|-----------|-------|
| Status | `26 01 00 00 FF D9` | Read device status |
| Energy | `26 23 00 00 FF B7` | Read battery/solar info |
| Device info | `26 11 00 00 FF C9` | Read model/firmware |
| Line 1 ON N min | `26 02 01 04 01 [N] 00 00 FF [chk]` | |
| Line 2 ON N min | `26 02 01 04 00 00 01 [N] FF [chk]` | |
| Stop all | `26 02 01 04 00 00 00 00 FF D3` | |

### Response Format

```
23 [type] [status] [length] [data...] [separator] [checksum]
```

| Status | Meaning |
|--------|---------|
| `0x00` | Success |
| `0x01` | Wrong PIN |
| `0x10` | Format/structure error |
| `0x20` | Not authenticated |

---

## BLE Broadcast (Passive Monitoring)

The device continuously advertises manufacturer-specific data. No connection required.

The BLE "company ID" field is **repurposed as data** (not a real Bluetooth SIG identifier).

### Raw Structure (9 bytes)

```
[counter] [solar] [status] [L1_min] [L2_min] [flags] [MAC_hi] [MAC_mid] [MAC_lo]
└── company_id LE16 ──┘ └──────────── manufacturer data (7 bytes) ──────────────┘
```

| Field | Source | Description |
|-------|--------|-------------|
| Counter | company_id & 0xFF | Rolling sequence number (ignore) |
| Solar irradiance | company_id >> 8 | Raw sensor value 0–255 |
| Status byte | data[0] | Bit 5 (0x20)=L1 active, Bit 7 (0x80)=L2 active, bits[4:0]=energy level |
| L1 remaining | data[1] | Minutes left on Line 1 timer (0=off) |
| L2 remaining | data[2] | Minutes left on Line 2 timer (0=off) |
| Flags | data[3] | Hardware flags (observed: 0x81) |
| MAC suffix | data[4:7] | Last 3 bytes of device MAC |

### Solar Irradiance Thresholds (confirmed empirically)

| Raw Value | Label | Conditions |
|-----------|-------|------------|
| ≥ 150 | Excellent | Direct sunlight |
| 50 – 149 | Good | Bright / partial sun |
| 5 – 49 | Sufficient | Overcast / shade |
| 1 – 4 | Poor | Very dark / dusk |
| 0 | None | Night |

### Battery Level (from status byte lower 5 bits)

| Value | Label |
|-------|-------|
| ≥ 0x0D | Excellent |
| 0x0B – 0x0C | Good |
| 0x08 – 0x0A | Sufficient |
| 0x05 – 0x07 | Energy Saving |
| 0x01 – 0x04 | Insufficient |
| 0x00 | Data Unavailable |

---

## Repository Structure

```
claber_ble_research/
├── README.md               ← Protocol documentation (this file)
├── requirements.txt        ← Python dependencies (bleak)
├── claber_protocol.py      ← Protocol library: auth, commands, broadcast decoding
├── valve_demo.py           ← Working demo: pair + control valves (L1/L2 cycle)
├── e2e_test.py             ← End-to-end test: auth + read status/energy
├── live_broadcast.py       ← Passive broadcast decoder (no connection needed)
```

---

## Quick Start

```bash
cd claber_ble_research
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Monitor device broadcasts (no pairing needed)
python live_broadcast.py

# Control valves (requires device in range)
python valve_demo.py

# Library usage
python -c "
from claber_protocol import build_auth_packet, build_valve_command, decode_broadcast
auth = build_auth_packet('YOUR_PIN_HERE')
cmd = build_valve_command(line1_on=True, line1_minutes=15)
print(f'Auth: {auth.hex()}')
print(f'Valve: {cmd.hex()}')
"
```

---

## Next Steps

- [ ] Home Assistant HACS integration (BLE proxy compatible)
- [ ] Enumerate remaining 251 key streams (device oracle or binary extraction)
- [ ] Decode flags byte fully (rain sensor? hardware variant?)
- [ ] Test with single-line model (PIN suffix 'E')
