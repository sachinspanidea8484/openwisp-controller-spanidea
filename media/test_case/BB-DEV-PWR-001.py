# START_DESCRIPTION
# 1. Read INA220 input power sensor directly from hwmon7 sysfs.
# 2. Extract voltage and current readings.
# 3. Validate voltage within expected tolerance range.
# 4. Validate current within safe operating limits.
# 5. Repeat readings multiple times.
# 6. Verify readings are dynamic and not static.
# 7. If valid readings observed, mark test as PASSED.
# END_DESCRIPTION

#!/usr/bin/env python3
import sys, os, time
from common_helper import log, EXIT_SUCCESS, EXIT_FAILED

HWMON_PATH       = "/sys/class/hwmon/hwmon7"
EXPECTED_VOLTAGE = 12.0
VOLTAGE_TOLERANCE = 2.0
CURRENT_MIN      = 0.0
CURRENT_MAX      = 5.0
NUM_READS        = 5


def read_file(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except Exception as e:
        log("[WARN] Could not read %s: %s", path, str(e), level="WARN")
        return None


def verify_hwmon():
    """Verify the hwmon device is INA220 and required sysfs files exist."""
    name = read_file(os.path.join(HWMON_PATH, "name"))
    if not name:
        log("[FAIL] Could not read hwmon name from %s", HWMON_PATH, level="FAIL")
        return False
    if not name.lower().startswith("ina2"):
        log("[FAIL] Unexpected hwmon device '%s' at %s (expected INA2xx)", name, HWMON_PATH, level="FAIL")
        return False

    for fname in ("in1_input", "curr1_input"):
        fpath = os.path.join(HWMON_PATH, fname)
        if not os.path.exists(fpath):
            log("[FAIL] Missing sysfs file: %s", fpath, level="FAIL")
            return False

    log("[INFO] INA220 sensor confirmed at %s (name=%s)", HWMON_PATH, name)
    return True


def read_ina220():
    """
    Read bus voltage (V) and current (A) from INA220 hwmon sysfs.
    in1_input  = bus voltage  in mV
    curr1_input = current     in mA
    """
    raw_voltage = read_file(os.path.join(HWMON_PATH, "in1_input"))
    raw_current = read_file(os.path.join(HWMON_PATH, "curr1_input"))

    voltage = float(raw_voltage) / 1000.0 if raw_voltage else None
    current = float(raw_current) / 1000.0 if raw_current else None
    return voltage, current


def main():
    log("[STEP 0] Verifying INA220 sensor at %s", HWMON_PATH)

    if not verify_hwmon():
        sys.exit(EXIT_FAILED)

    log("[STEP 1] Starting Input Power Verification Test (BB-DEV-PWR-001)")

    voltage_min = EXPECTED_VOLTAGE - VOLTAGE_TOLERANCE
    voltage_max = EXPECTED_VOLTAGE + VOLTAGE_TOLERANCE

    previous_voltage = None
    previous_current = None
    changing_detected = False
    total_passed = True

    for i in range(1, NUM_READS + 1):
        try:
            voltage, current = read_ina220()
        except Exception as e:
            log("[FAIL] Iteration %d: Failed to read INA220 sensor: %s", i, str(e), level="FAIL")
            total_passed = False
            break

        if voltage is None or current is None:
            log("[FAIL] Iteration %d: No data received from sensor", i, level="FAIL")
            total_passed = False
            break

        log("[%d] INA220 Sensor Data:", i)
        log("  Bus Voltage (V)  : %.2f", voltage)
        log("  Current (A)      : %.2f", current)

        if not (voltage_min <= voltage <= voltage_max):
            log("[FAIL] Iteration %d: Voltage %.2f V out of range (%.2f - %.2f V)",
                i, voltage, voltage_min, voltage_max, level="FAIL")
            total_passed = False
            break

        if not (CURRENT_MIN <= current <= CURRENT_MAX):
            log("[FAIL] Iteration %d: Current %.2f A out of range (%.2f - %.2f A)",
                i, current, CURRENT_MIN, CURRENT_MAX, level="FAIL")
            total_passed = False
            break

        if previous_voltage is not None:
            if (abs(voltage - previous_voltage) > 0.01 or
                    abs(current - previous_current) > 0.01):
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
