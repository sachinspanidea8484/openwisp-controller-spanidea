#!/usr/bin/env python3
import sys, time, re
from common_helper import log, run_local_command, verify_file_exists, EXIT_SUCCESS, EXIT_FAILED

SENSOR_SCRIPT = "/usr/bin/sensor_monitor.py"
TARGET_SENSOR = "SHT4X_HWMON0"
NUM_READINGS, DELAY = 5, 1
TEMP_MIN, TEMP_MAX = -45, 80


def extract_block(out):
    m = re.search(r"SHT4X_HWMON0\s*\n(?: {2}.+\n?){2,5}", out)
    return m.group(0).strip() if m else None


def parse_values(block):
    t = re.search(r"Temperature\s*\(.*C\)\s*:\s*([\d\.\-]+)", block)
    h = re.search(r"Humidity\s*\(.*\)\s*:\s*([\d\.\-]+)", block)
    return (float(t.group(1)) if t else None,
            float(h.group(1)) if h else None)


def main():
    log("[STEP 1] Starting SHT4X Temperature & Humidity Test")
    if not verify_file_exists(SENSOR_SCRIPT): sys.exit(EXIT_FAILED)

    readings = []

    for i in range(1, NUM_READINGS + 1):
        out, _, rc = run_local_command(f"python3 {SENSOR_SCRIPT}", allow_fail=True)
        if rc != 0 or not out:
            log("[FAIL] No sensor output", level="FAIL"); sys.exit(EXIT_FAILED)

        block = extract_block(out)
        if not block:
            log("[FAIL] %s block not found", TARGET_SENSOR, level="FAIL"); sys.exit(EXIT_FAILED)

        log("[%d] Retrieved %s Data:", i, TARGET_SENSOR)
        for l in block.splitlines(): log("%s", l)

        temp, hum = parse_values(block)
        if temp is None or hum is None:
            log("[FAIL] Could not parse Temperature/Humidity", level="FAIL"); sys.exit(EXIT_FAILED)

        if not (TEMP_MIN <= temp <= TEMP_MAX):
            log("[FAIL] Temperature %.2f°C out of range (%d-%d°C)",
                temp, TEMP_MIN, TEMP_MAX, level="FAIL"); sys.exit(EXIT_FAILED)

        readings.append((temp, hum))
        time.sleep(DELAY)

    if len(readings)==NUM_READINGS and all(r==readings[0] for r in readings):
        log("[FAIL] All readings identical. Sensor not updating.", level="FAIL")
        sys.exit(EXIT_FAILED)

    log("[PASS] SHT4X Temperature & Humidity Test PASSED", level="PASS")
    sys.exit(EXIT_SUCCESS)


if __name__ == "__main__":
    main()

