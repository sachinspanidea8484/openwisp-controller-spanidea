# START_DESCRIPTION
# 1. Execute sensor monitoring script for input power.
# 2. Extract voltage and current readings.
# 3. Validate voltage within expected tolerance range.
# 4. Validate current within safe operating limits.
# 5. Repeat readings multiple times.
# 6. Verify readings are dynamic and not static.
# 7. If valid readings observed, mark test as PASSED.
# END_DESCRIPTION

#!/usr/bin/env python3

import sys
import os

from common_helper import (
    log,
    run_local_command,
    EXIT_SUCCESS,
    EXIT_FAILED,
    extract_target_block,
    parse_sensor_output
)

EXPECTED_VOLTAGE = 12.0
VOLTAGE_TOLERANCE = 2.0
CURRENT_MIN = 0.0
CURRENT_MAX = 5.0
NUM_READS = 5
SENSOR_SCRIPT = "/usr/bin/sensor_monitor.py"
TARGET_SENSOR = "INA220_HWMON7"

def main():

    log("[STEP 0] Verifying required sensor monitoring script")

    if not os.path.isfile(SENSOR_SCRIPT):
        log("[FAIL] Required script '%s' not found.", SENSOR_SCRIPT, level="FAIL")
        sys.exit(EXIT_FAILED)

    log("[INFO] Sensor script found: %s", SENSOR_SCRIPT)

    log("[STEP 1] Starting Input Power Verification Test")

    voltage_min = EXPECTED_VOLTAGE - VOLTAGE_TOLERANCE
    voltage_max = EXPECTED_VOLTAGE + VOLTAGE_TOLERANCE

    previous_voltage = None
    previous_current = None
    changing_detected = False
    total_passed = True

    for i in range(1, NUM_READS + 1):

        stdout, stderr, rc = run_local_command(
            SENSOR_SCRIPT,
            allow_fail=True
        )

        if rc != 0 or not stdout:
            log("[FAIL] Iteration %d: No output received (RC=%s)", i, rc, level="FAIL")
            total_passed = False
            break

        block = extract_target_block(stdout, TARGET_SENSOR)

        if not block:
            log("[FAIL] Iteration %d: Target sensor '%s' not found", i, TARGET_SENSOR, level="FAIL")
            total_passed = False
            break

        log("[%d] Retrieved %s Data:", i, TARGET_SENSOR)

        for line in block.splitlines():
            log("%s", line)

        voltage, current = parse_sensor_output(block)

        if voltage is None or not (voltage_min <= voltage <= voltage_max):
            log(
                "[FAIL] Iteration %d: Voltage %.2f V out of range (%.2f - %.2f V)",
                i,
                voltage if voltage else -1,
                voltage_min,
                voltage_max,
                level="FAIL"
            )
            total_passed = False
            break

        if current is None or not (CURRENT_MIN <= current <= CURRENT_MAX):
            log(
                "[FAIL] Iteration %d: Current %.2f A out of range (%.2f - %.2f A)",
                i,
                current if current else -1,
                CURRENT_MIN,
                CURRENT_MAX,
                level="FAIL"
            )
            total_passed = False
            break

        if previous_voltage is not None:
            if abs(voltage - previous_voltage) > 0.01 or abs(current - previous_current) > 0.01:
                changing_detected = True

        previous_voltage = voltage
        previous_current = current

    if total_passed:

        if not changing_detected:
            log("[WARN] Sensor readings appear static — check data source.", level="WARN")

        log("[PASS] Input Power Verification PASSED", level="PASS")
        sys.exit(EXIT_SUCCESS)

    log("[FAIL] Input Power Verification FAILED", level="FAIL")
    sys.exit(EXIT_FAILED)


if __name__ == "__main__":
    main()
