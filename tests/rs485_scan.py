#!/usr/bin/env python3
# MIT License
# Copyright (c) by Dan Luca. All rights reserved.
"""
rs485_scan.py — RS485 bus connectivity probe for GardenPy using the dfrobot sensor classes.

Run directly on the Raspberry Pi (from the project root with the package installed):

    python3 tests/rs485_scan.py [--port /dev/serial0] [--baud 9600]

Probes every sensor configured in the system (Z1/Z2/Z3 SEN0604 soil sensors,
Z2 SEN0605 NPK sensor, ENV SEN0438 air sensor) via the same Sensor classes used
in production, and prints a clear PASS/FAIL table with live register readings.
Exit code is 0 only when all sensors respond.
"""

import argparse
import sys
import time

try:
    import serial
    from waterly.dfrobot import SEN0604, SEN0605, SEN0438
except ImportError as e:
    print(f"ERROR: Missing dependency — {e}")
    print("Install the waterly package first:  pip install -e .")
    sys.exit(2)

# ─── Bus defaults ─────────────────────────────────────────────────────────────
DEFAULT_PORT    = "/dev/serial0"
DEFAULT_BAUD    = 9600
DEFAULT_TIMEOUT = 1.5   # seconds; slightly more generous than production 1.25s

# ─── Sensor catalogue ─────────────────────────────────────────────────────────
# (display_name, sensor_class, modbus_address)
# Addresses match the values stored in the DB (core_v1.0.1.sql)
SENSORS = [
    ("Z1  Soil  SEN0604", SEN0604, 0x0A),
    ("Z2  Soil  SEN0604", SEN0604, 0x0B),
    ("Z3  Soil  SEN0604", SEN0604, 0x0C),
    ("Z2  NPK   SEN0605", SEN0605, 0x20),
    ("ENV Air   SEN0438", SEN0438, 0x30),
]

# ─── Display formatters keyed on ReadingType enum members ─────────────────────
_FORMATTERS = {
    SEN0604.ReadingType.MOISTURE:                lambda v: f"{v:.1f} %",
    SEN0604.ReadingType.TEMPERATURE:             lambda v: f"{v:.1f} °C",
    SEN0604.ReadingType.ELECTRICAL_CONDUCTIVITY: lambda v: f"{v} µS/cm",
    SEN0604.ReadingType.PH:                      lambda v: f"{v:.1f}",
    SEN0604.ReadingType.SALINITY:                lambda v: f"{v}",
    SEN0604.ReadingType.TOTAL_DISSOLVED_SOLIDS:  lambda v: f"{v} mg/L",
    SEN0605.ReadingType.NITROGEN:                lambda v: f"{v} mg/kg",
    SEN0605.ReadingType.PHOSPHORUS:              lambda v: f"{v} mg/kg",
    SEN0605.ReadingType.POTASSIUM:               lambda v: f"{v} mg/kg",
    SEN0438.ReadingType.HUMIDITY:                lambda v: f"{v:.1f} %",
    SEN0438.ReadingType.AIR_TEMPERATURE:         lambda v: f"{v:.1f} °C",
}

# ─── Probe helpers ────────────────────────────────────────────────────────────

def probe_sensor(sensor_cls, addr: int, port: str, baud: int, timeout: float) -> tuple[bool, list]:
    """
    Instantiate one sensor, test connectivity and read all values, then close it.

    Each sensor opens the serial port independently in its constructor, so sensors
    must be probed sequentially (open → test → close → next).

    Returns (passed, readings) where readings is a list of (label, display_str) pairs.
    """
    sensor = sensor_cls(deviceaddr=addr, port=port, baudrate=baud, timeout=timeout)
    try:
        sensor.open()
        passed = sensor.is_connected()
        readings = []
        if passed:
            try:
                for rtype, value in sensor.read_all().items():
                    fmt = _FORMATTERS.get(rtype, str)
                    readings.append((rtype.value, fmt(value)))
            except Exception as exc:
                readings.append(("read_all", f"ERROR: {exc}"))
        else:
            readings.append(("is_connected", "no response"))
        return passed, readings
    except Exception as e1:
        return False, [("probe", f"ERROR: {e1}")]
    finally:
        sensor.close()


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Probe all GardenPy sensors on the RS485 bus using the dfrobot Sensor classes."
    )
    parser.add_argument("--port",    default=DEFAULT_PORT,    help=f"Serial port (default: {DEFAULT_PORT})")
    parser.add_argument("--baud",    default=DEFAULT_BAUD,    type=int, help=f"Baud rate (default: {DEFAULT_BAUD})")
    parser.add_argument("--timeout", default=DEFAULT_TIMEOUT, type=float, help=f"Read timeout in seconds (default: {DEFAULT_TIMEOUT})")
    args = parser.parse_args()

    print(f"\nGardenPy RS485 Bus Scan  —  port={args.port}  baud={args.baud}  timeout={args.timeout}s")
    print("=" * 72)

    results = []   # (name, addr, passed, readings)

    for name, sensor_cls, addr in SENSORS:
        print(f"\n  [{name}]  addr=0x{addr:02X} ({addr})")
        try:
            passed, readings = probe_sensor(sensor_cls, addr, args.port, args.baud, args.timeout)
        except serial.SerialException as exc:
            print(f"\nFATAL: Cannot open {args.port} — {exc}")
            print("Check: is the RS485 adapter enabled? (raspi-config → Interface Options → Serial Port)")
            sys.exit(2)

        if not passed:
            print(f"    FAIL  — no response from sensor {readings[0][0]}: {readings[0][1]}")
        else:
            for label, display in readings:
                print(f"    ok    {label:<30}  {display}")
        results.append((name, addr, passed, readings))
        time.sleep(0.25)   # brief pause between sensors

    # ─── Summary ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 72)
    print("Summary")
    print("-" * 72)
    passed_count = 0
    for name, addr, passed, _ in results:
        status = "PASS" if passed else "FAIL"
        if passed:
            passed_count += 1
        print(f"  {status}  0x{addr:02X}  {name}")

    total = len(results)
    print("-" * 72)
    print(f"  {passed_count}/{total} sensors responding")

    if passed_count < total:
        print("\nTroubleshooting hints:")
        print("  • Is the Serial Hardware (RS485 adapter) enabled? (raspi-config → Interface Options → Serial Port: Disable Serial Login Shell, Enable Serial Hardware Port)")
        print("  • Verify 12V power to the RS485 sensor rail")
        print("  • Check A/B wiring polarity on the bus connector")
        print("  • Confirm termination resistor is present if cable >1 m")
        print("  • Make sure no other process has /dev/serial0 open (stop waterly first)")
        print("  • Each SEN0604 ships at address 0x01 — if never configured, addresses")
        print("    0x0A/0x0B/0x0C may not match.  Scan address 0x01 to find an unconfigured sensor.")
        sys.exit(1)

    print("\nAll sensors OK.")
    sys.exit(0)


if __name__ == "__main__":
    main()