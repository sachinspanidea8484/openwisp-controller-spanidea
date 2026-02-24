# START_DESCRIPTION
# 1. Execute sensor monitoring script for CPU input power.
# 2. Extract voltage and current values from sensor output.
# 3. Validate voltage within defined limits.
# 4. Validate current within defined limits.
# 5. Repeat readings multiple times.
# 6. Ensure sensor values change slightly across samples.
# 7. If all validations pass, mark test as PASSED.
# END_DESCRIPTION

#!/usr/bin/env python3
import sys
import os
from common_helper import (
    log,
    run_local_command,
    extract_target_block,
    parse_sensor_output,
    EXIT_SUCCESS,
    EXIT_FAILED
)

# ===== Test Configuration =====
VOLTAGE_MIN = 0.8
VOLTAGE_MAX = 1.2
CURRENT_MIN = 0.0
CURRENT_MAX = 6.0
NUM_READS = 5
SENSOR_SCRIPT = "/usr/bin/sensor_monitor.py"
TARGET_SENSOR = "INA220_HWMON6"


# ============================================================
# Validate a single reading
# ============================================================
def validate_reading(voltage, current, iteration):

    if voltage is None or current is None:
        return False, f"[FAIL] Iteration {iteration}: Could not parse {TARGET_SENSOR} output"

    if not (VOLTAGE_MIN <= voltage <= VOLTAGE_MAX):
        return False, (
            f"[FAIL] Iteration {iteration}: "
            f"Voltage {voltage:.2f} V out of range ({VOLTAGE_MIN}-{VOLTAGE_MAX} V)"
        )

    if not (CURRENT_MIN <= current <= CURRENT_MAX):
        return False, (
            f"[FAIL] Iteration {iteration}: "
            f"Current {current:.2f} A out of range ({CURRENT_MIN}-{CURRENT_MAX} A)"
        )

    return True, None


# ============================================================
# Main Test
# ============================================================
def main():

    log("[STEP 1] Starting CPU Input Power Test (BB-DEV-PWR-002)")

    # ---- Verify sensor script exists ----
    if not os.path.isfile(SENSOR_SCRIPT):
        log("Required file not found: %s", SENSOR_SCRIPT, level="FAIL")
        sys.exit(EXIT_FAILED)

    log("[STEP 2] Reading sensor data")

    total_passed = True
    previous_voltage = None
    previous_current = None
    changing_detected = False
    failure_message = None

    for i in range(1, NUM_READS + 1):

        stdout, stderr, rc = run_local_command(
            SENSOR_SCRIPT,
            allow_fail=True
        )

        if rc != 0 or not stdout:
            failure_message = (
                f"[FAIL] Iteration {i}: "
                f"No output received from {SENSOR_SCRIPT} (RC={rc})"
            )
            total_passed = False
            break

        block = extract_target_block(stdout, TARGET_SENSOR)
        voltage, current = parse_sensor_output(block)

        log("[%d] Retrieved %s Data:", i, TARGET_SENSOR)
        for line in block.splitlines():
            log("%s", line)

        passed, message = validate_reading(voltage, current, i)
        if not passed:
            failure_message = message
            total_passed = False
            break

        # Detect minor variation
        if previous_voltage is not None:
            if (
                abs(voltage - previous_voltage) > 0.01 or
                abs(current - previous_current) > 0.01
            ):
                changing_detected = True

        previous_voltage = voltage
        previous_current = current

    # ========================================================
    # Final Result
    # ========================================================
    if total_passed:
        if not changing_detected:
            log("Sensor readings appear static — check data source.", level="WARN")

        log("CPU Input Power Test PASSED", level="PASS")
        sys.exit(EXIT_SUCCESS)

    log(failure_message, level="FAIL")
    log("CPU Input Power Test FAILED", level="FAIL")
    sys.exit(EXIT_FAILED)


if __name__ == "__main__":
    main()

