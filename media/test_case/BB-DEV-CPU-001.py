#!/usr/bin/env python3
import sys, time, re
from common_helper import log, run_local_command, verify_file_exists, EXIT_SUCCESS, EXIT_FAILED
SENSOR_SCRIPT = "/usr/bin/sensor_monitor.py"
TARGET_SENSOR = "SA56004_HWMON8"
READING_COUNT = 5
TEMP_MIN, TEMP_MAX = -45, 80

def extract_block(out):
    m = re.search(r"(SA56004_HWMON8.*?)(?=\n\S|$)", out, re.DOTALL)
    return m.group(1).strip() if m else None

def parse_temp(block):
    l = re.search(r"Local\s+Temp.*?:\s*([\d\.]+)", block)
    r = re.search(r"Remote\s+Temp.*?:\s*([\d\.]+)", block)
    return (float(l.group(1)) if l else None,
            float(r.group(1)) if r else None)

def main():
    log("[STEP 1] Starting SA56004_HWMON8 Temperature Test")
    if not verify_file_exists(SENSOR_SCRIPT): sys.exit(EXIT_FAILED)
    readings = []
    for i in range(1, READING_COUNT + 1):
        out, err, rc = run_local_command(f"python3 {SENSOR_SCRIPT}", allow_fail=True)
        if rc != 0:
            log("[FAIL] Sensor command failed: %s", err, level="FAIL"); sys.exit(EXIT_FAILED)

        block = extract_block(out)
        if not block:
            log("[FAIL] %s block not found", TARGET_SENSOR, level="FAIL"); sys.exit(EXIT_FAILED)

        log("[%d] Retrieved %s Data:", i, TARGET_SENSOR)
        for l in block.splitlines(): log("%s", l)

        local, remote = parse_temp(block)
        if local is None or remote is None:
            log("[FAIL] Could not parse temperatures", level="FAIL"); sys.exit(EXIT_FAILED)

        if not (TEMP_MIN <= local <= TEMP_MAX):
            log("[FAIL] Local Temp %.2f°C out of range", local, level="FAIL"); sys.exit(EXIT_FAILED)

        if not (TEMP_MIN <= remote <= TEMP_MAX):
            log("[FAIL] Remote Temp %.2f°C out of range", remote, level="FAIL"); sys.exit(EXIT_FAILED)

        readings.append((local, remote))
        time.sleep(1)

    if len(readings)==READING_COUNT and all(r==readings[0] for r in readings):
        log("[FAIL] All readings identical. Sensor not updating.", level="FAIL")
        sys.exit(EXIT_FAILED)

    log("[PASS] SA56004_HWMON8 Temperature Test PASSED", level="PASS")
    sys.exit(EXIT_SUCCESS)


if __name__ == "__main__":
    main()

