# START_DESCRIPTION
# 1. Read SA56004 CPU temperature sensor directly from hwmon sysfs.
# 2. Extract Local and Remote temperature values.
# 3. Validate temperature within defined operating range.
# 4. Repeat readings multiple times.
# 5. Ensure temperature values are not static.
# 6. If readings valid and dynamic, mark test as PASSED.
# END_DESCRIPTION

#!/usr/bin/env python3
import sys, os, time
from common_helper import log, EXIT_SUCCESS, EXIT_FAILED

HWMON_PATH    = "/sys/class/hwmon/hwmon8"
READING_COUNT = 5
TEMP_MIN      = -45
TEMP_MAX      = 80


def read_file(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except Exception as e:
        log("[WARN] Could not read %s: %s", path, str(e), level="WARN")
        return None


def verify_hwmon():
    """Verify the hwmon device is SA56004 and required sysfs files exist."""
    name = read_file(os.path.join(HWMON_PATH, "name"))
    if not name:
        log("[FAIL] Could not read hwmon name from %s", HWMON_PATH, level="FAIL")
        return False
    if name.lower() != "sa56004":
        log("[FAIL] Unexpected hwmon device '%s' at %s (expected sa56004)", name, HWMON_PATH, level="FAIL")
        return False

    for fname in ("temp1_input", "temp2_input"):
        fpath = os.path.join(HWMON_PATH, fname)
        if not os.path.exists(fpath):
            log("[FAIL] Missing sysfs file: %s", fpath, level="FAIL")
            return False

    log("[INFO] SA56004 sensor confirmed at %s", HWMON_PATH)
    return True


def read_sa56004():
    """Read local and remote temperatures (°C) from SA56004 hwmon sysfs."""
    raw_local  = read_file(os.path.join(HWMON_PATH, "temp1_input"))
    raw_remote = read_file(os.path.join(HWMON_PATH, "temp2_input"))

    local  = float(raw_local)  / 1000.0 if raw_local  else None
    remote = float(raw_remote) / 1000.0 if raw_remote else None
    return local, remote


def main():
    log("[STEP 1] Starting SA56004 CPU Temperature Test (BB-DEV-CPU-001)")

    if not verify_hwmon():
        sys.exit(EXIT_FAILED)

    readings = []

    for i in range(1, READING_COUNT + 1):
        try:
            local, remote = read_sa56004()
        except Exception as e:
            log("[FAIL] Iteration %d: Failed to read SA56004 sensor: %s", i, str(e), level="FAIL")
            sys.exit(EXIT_FAILED)

        if local is None or remote is None:
            log("[FAIL] Iteration %d: Could not parse temperatures", i, level="FAIL")
            sys.exit(EXIT_FAILED)

        log("[%d] SA56004 Sensor Data:", i)
        log("  Local Temp  (°C) : %.2f", local)
        log("  Remote Temp (°C) : %.2f", remote)

        if not (TEMP_MIN <= local <= TEMP_MAX):
            log("[FAIL] Iteration %d: Local Temp %.2f°C out of range (%d-%d°C)",
                i, local, TEMP_MIN, TEMP_MAX, level="FAIL")
            sys.exit(EXIT_FAILED)

        if not (TEMP_MIN <= remote <= TEMP_MAX):
            log("[FAIL] Iteration %d: Remote Temp %.2f°C out of range (%d-%d°C)",
                i, remote, TEMP_MIN, TEMP_MAX, level="FAIL")
            sys.exit(EXIT_FAILED)

        readings.append((local, remote))
        time.sleep(1)

    if len(readings) == READING_COUNT and all(r == readings[0] for r in readings):
        log("[FAIL] All readings identical. Sensor not updating.", level="FAIL")
        sys.exit(EXIT_FAILED)

    log("[PASS] SA56004 CPU Temperature Test PASSED", level="PASS")
    sys.exit(EXIT_SUCCESS)


if __name__ == "__main__":
    main()
