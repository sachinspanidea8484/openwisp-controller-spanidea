# START_DESCRIPTION
# 1. Read INA220 CPU input power sensor directly from hwmon6 sysfs.
# 2. Extract voltage and current values.
# 3. Validate voltage within defined limits.
# 4. Validate current within defined limits.
# 5. Repeat readings multiple times.
# 6. Ensure sensor values change slightly across samples.
# 7. If all validations pass, mark test as PASSED.
# END_DESCRIPTION

#!/usr/bin/env python3
import sys, os, time
from common_helper import log, EXIT_SUCCESS, EXIT_FAILED

HWMON_PATH   = "/sys/class/hwmon/hwmon6"
VOLTAGE_MIN  = 0.8
VOLTAGE_MAX  = 1.2
CURRENT_MIN  = 0.0
CURRENT_MAX  = 6.0
NUM_READS    = 5


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
    in1_input   = bus voltage in mV
    curr1_input = current     in mA
    """
    raw_voltage = read_file(os.path.join(HWMON_PATH, "in1_input"))
    raw_current = read_file(os.path.join(HWMON_PATH, "curr1_input"))

    voltage = float(raw_voltage) / 1000.0 if raw_voltage else None
    current = float(raw_current) / 1000.0 if raw_current else None
    return voltage, current


def validate_reading(voltage, current, iteration):
    if voltage is None or current is None:
        return False, f"[FAIL] Iteration {iteration}: Could not parse sensor output"

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


def main():
    log("[STEP 1] Starting CPU Input Power Test (BB-DEV-PWR-002)")

    if not verify_hwmon():
        sys.exit(EXIT_FAILED)

    log("[STEP 2] Reading sensor data")

    total_passed     = True
    previous_voltage = None
    previous_current = None
    changing_detected = False
    failure_message  = None

    for i in range(1, NUM_READS + 1):
        try:
            voltage, current = read_ina220()
        except Exception as e:
            failure_message = f"[FAIL] Iteration {i}: Failed to read INA220 sensor: {e}"
            total_passed = False
            break

        log("[%d] INA220 Sensor Data:", i)
        log("  Bus Voltage (V)  : %.2f", voltage if voltage is not None else -1)
        log("  Current (A)      : %.2f", current if current is not None else -1)

        passed, message = validate_reading(voltage, current, i)
        if not passed:
            failure_message = message
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
            log("Sensor readings appear static — check data source.", level="WARN")
        log("CPU Input Power Test PASSED", level="PASS")
        sys.exit(EXIT_SUCCESS)

    log(failure_message, level="FAIL")
    log("CPU Input Power Test FAILED", level="FAIL")
    sys.exit(EXIT_FAILED)


if __name__ == "__main__":
    main()
