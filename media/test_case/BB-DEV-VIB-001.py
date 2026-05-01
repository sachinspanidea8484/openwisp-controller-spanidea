# START_DESCRIPTION
# 1. Read IMU/vibration sensor data directly from IIO sysfs interface.
# 2. Collect Gyroscope and Accelerometer raw values and scale factors.
# 3. Compute calibrated sensor readings.
# 4. Repeat sensor readings multiple times.
# 5. Verify readings show variation across iterations.
# 6. If variation detected, mark test as PASSED.
# END_DESCRIPTION

#!/usr/bin/env python3
import sys, os, time
from common_helper import log, EXIT_SUCCESS, EXIT_FAILED

GYRO_PATH  = "/sys/bus/iio/devices/iio:device0"
ACCEL_PATH = "/sys/bus/iio/devices/iio:device1"
NUM_READS  = 5


def read_val(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except Exception as e:
        log("[WARN] Could not read %s: %s", path, str(e), level="WARN")
        return "0"


def verify_iio_paths():
    """Verify required IIO device paths exist."""
    required = [
        f"{GYRO_PATH}/in_anglvel_x_raw",
        f"{GYRO_PATH}/in_anglvel_y_raw",
        f"{GYRO_PATH}/in_anglvel_z_raw",
        f"{GYRO_PATH}/in_anglvel_scale",
        f"{ACCEL_PATH}/in_accel_x_raw",
        f"{ACCEL_PATH}/in_accel_y_raw",
        f"{ACCEL_PATH}/in_accel_z_raw",
        f"{ACCEL_PATH}/in_accel_scale",
    ]
    missing = [p for p in required if not os.path.exists(p)]
    if missing:
        for m in missing:
            log("[FAIL] Missing IIO sysfs path: %s", m, level="FAIL")
        return False
    return True


def read_imu():
    """Read gyroscope and accelerometer data directly from IIO sysfs."""
    gyro_scale = float(read_val(f"{GYRO_PATH}/in_anglvel_scale"))
    gyro_raw = {
        "x": int(read_val(f"{GYRO_PATH}/in_anglvel_x_raw")),
        "y": int(read_val(f"{GYRO_PATH}/in_anglvel_y_raw")),
        "z": int(read_val(f"{GYRO_PATH}/in_anglvel_z_raw")),
    }
    gyro = {k: round(v * gyro_scale, 3) for k, v in gyro_raw.items()}

    accel_scale = float(read_val(f"{ACCEL_PATH}/in_accel_scale"))
    accel_raw = {
        "x": int(read_val(f"{ACCEL_PATH}/in_accel_x_raw")),
        "y": int(read_val(f"{ACCEL_PATH}/in_accel_y_raw")),
        "z": int(read_val(f"{ACCEL_PATH}/in_accel_z_raw")),
    }
    accel = {k: round(v * accel_scale, 3) for k, v in accel_raw.items()}

    return gyro, accel


def main():
    log("[STEP 0] Verifying IIO sysfs sensor paths")

    if not verify_iio_paths():
        log("[FAIL] One or more required IIO sysfs paths are missing.", level="FAIL")
        sys.exit(EXIT_FAILED)

    log("[STEP 1] Starting Vibration/IMU Sensor Test (BB-DEV-VIB-001)")

    readings = []

    for i in range(1, NUM_READS + 1):
        try:
            gyro, accel = read_imu()
        except Exception as e:
            log("[FAIL] Iteration %d: Failed to read IMU sensor: %s", i, str(e), level="FAIL")
            sys.exit(EXIT_FAILED)

        log("[INFO] Raw Sensor Data (iteration %d):", i)
        log("Gyro : %s", gyro)
        log("Accel: %s", accel)
        log("[PARSED] Iteration %d ... Gyro: %s, Accel: %s", i, gyro, accel)

        readings.append((gyro, accel))
        time.sleep(1)

    if all(r == readings[0] for r in readings):
        log("[FAIL] All vibration readings identical. No variation detected.", level="FAIL")
        sys.exit(EXIT_FAILED)

    log("[PASS] Vibration readings show variation across samples.", level="PASS")
    log("[RESULT] SUCCESS ... Vibration/IMU sensor verification passed.", level="PASS")
    sys.exit(EXIT_SUCCESS)


if __name__ == "__main__":
    main()
