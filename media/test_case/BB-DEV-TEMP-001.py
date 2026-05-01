# START_DESCRIPTION
# 1. Read SHT4X temperature and humidity sensor directly from hwmon sysfs.
# 2. Extract Temperature and Humidity values.
# 3. Validate temperature within acceptable range.
# 4. Collect multiple samples with delay.
# 5. Verify readings are not identical across samples.
# 6. If valid readings observed, mark test as PASSED.
# END_DESCRIPTION

#!/usr/bin/env python3
import sys, os, time
from common_helper import log, EXIT_SUCCESS, EXIT_FAILED

HWMON_PATH = "/sys/class/hwmon/hwmon0"
TEMP_MIN   = -45
TEMP_MAX   = 80
NUM_READINGS = 5
DELAY        = 1


def read_file(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except Exception as e:
        log("[WARN] Could not read %s: %s", path, str(e), level="WARN")
        return None


def verify_hwmon():
    """Verify the hwmon device is SHT4X and required sysfs files exist."""
    name = read_file(os.path.join(HWMON_PATH, "name"))
    if not name:
        log("[FAIL] Could not read hwmon name from %s", HWMON_PATH, level="FAIL")
        return False
    if not name.lower().startswith("sht4"):
        log("[FAIL] Unexpected hwmon device '%s' at %s (expected SHT4X)", name, HWMON_PATH, level="FAIL")
        return False

    for fname in ("temp1_input", "humidity1_input"):
        fpath = os.path.join(HWMON_PATH, fname)
        if not os.path.exists(fpath):
            log("[FAIL] Missing sysfs file: %s", fpath, level="FAIL")
            return False

    log("[INFO] SHT4X sensor confirmed at %s (name=%s)", HWMON_PATH, name)
    return True


def read_sht4x():
    """Read temperature (°C) and humidity (%RH) from SHT4X hwmon sysfs."""
    raw_temp = read_file(os.path.join(HWMON_PATH, "temp1_input"))
    raw_hum  = read_file(os.path.join(HWMON_PATH, "humidity1_input"))

    temp = float(raw_temp) / 1000.0 if raw_temp else None
    hum  = float(raw_hum)  / 1000.0 if raw_hum  else None
    return temp, hum


def main():
    log("[STEP 1] Starting SHT4X Temperature & Humidity Test")

    if not verify_hwmon():
        sys.exit(EXIT_FAILED)

    readings = []

    for i in range(1, NUM_READINGS + 1):
        try:
            temp, hum = read_sht4x()
        except Exception as e:
            log("[FAIL] Iteration %d: Failed to read SHT4X sensor: %s", i, str(e), level="FAIL")
            sys.exit(EXIT_FAILED)

        if temp is None or hum is None:
            log("[FAIL] Iteration %d: Could not parse Temperature/Humidity", i, level="FAIL")
            sys.exit(EXIT_FAILED)

        log("[%d] SHT4X Sensor Data:", i)
        log("  Temperature (°C)  : %.2f", temp)
        log("  Humidity (%%RH)    : %.2f", hum)

        if not (TEMP_MIN <= temp <= TEMP_MAX):
            log("[FAIL] Iteration %d: Temperature %.2f°C out of range (%d-%d°C)",
                i, temp, TEMP_MIN, TEMP_MAX, level="FAIL")
            sys.exit(EXIT_FAILED)

        readings.append((temp, hum))
        time.sleep(DELAY)

    if len(readings) == NUM_READINGS and all(r == readings[0] for r in readings):
        log("[FAIL] All readings identical. Sensor not updating.", level="FAIL")
        sys.exit(EXIT_FAILED)

    log("[PASS] SHT4X Temperature & Humidity Test PASSED", level="PASS")
    sys.exit(EXIT_SUCCESS)


if __name__ == "__main__":
    main()
