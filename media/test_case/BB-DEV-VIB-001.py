#!/usr/bin/env python3
import sys, os, time
from common_helper import log, run_local_command, EXIT_SUCCESS, EXIT_FAILED

SENSOR_SCRIPT = "/usr/bin/read_sensor.py"
NUM_READS = 5
GYRO_PATH = "/sys/bus/iio/devices/iio:device0"
ACCEL_PATH = "/sys/bus/iio/devices/iio:device1"


def read_val(path):   #read the value from the function
    try:
        with open(path) as f: return f.read().strip()
    except: return "0"


def fallback_read():
    start = time.time()

    gyro_raw = {k: int(read_val(f"{GYRO_PATH}/in_anglvel_{k}_raw")) for k in "xyz"}
    gyro_scale = float(read_val(f"{GYRO_PATH}/in_anglvel_scale"))
    gyro = {k: round(v * gyro_scale, 3) for k, v in gyro_raw.items()}

    accel_raw = {k: int(read_val(f"{ACCEL_PATH}/in_accel_{k}_raw")) for k in "xyz"}
    accel_scale = float(read_val(f"{ACCEL_PATH}/in_accel_scale"))
    accel = {k: round(v * accel_scale, 3) for k, v in accel_raw.items()}

    return f"Gyro: {gyro}\nAccel: {accel}\nRead time: {time.time()-start:.6f}s"


def parse_data(out):
    gyro = accel = None
    for line in out.splitlines():
        if line.startswith("Gyro:"): gyro = eval(line.replace("Gyro:", "").strip())
        elif line.startswith("Accel:"): accel = eval(line.replace("Accel:", "").strip())
    if not gyro or not accel: raise ValueError("Missing Gyro/Accel data")
    return gyro, accel


def main():
    log("[STEP 1] Starting Vibration/IMU Sensor Test (BB-DEV-VIB-001)")
    readings = []

    for i in range(1, NUM_READS + 1):

        if os.path.isfile(SENSOR_SCRIPT):
            out, err, rc = run_local_command(f"python3 {SENSOR_SCRIPT}", allow_fail=True)
            if rc != 0:
                log("[WARN] Sensor script failed, using fallback", level="WARN")
                out = fallback_read()
        else:
            out = fallback_read()

        log("[INFO] Raw Sensor Data (iteration %d):", i)
        for l in out.splitlines(): log("%s", l)

        try:
            gyro, accel = parse_data(out)
            log("[PARSED] Iteration %d ... Gyro: %s, Accel: %s", i, gyro, accel)
            readings.append((gyro, accel))
        except Exception as e:
            log("[FAIL] Iteration %d parse error: %s", i, str(e), level="FAIL")
            sys.exit(EXIT_FAILED)

        time.sleep(1)

    if all(r == readings[0] for r in readings):
        log("[FAIL] All vibration readings identical. No variation detected.", level="FAIL")
        sys.exit(EXIT_FAILED)

    log("[PASS] Vibration readings show variation across samples.", level="PASS")
    log("[RESULT] SUCCESS ... Vibration/IMU sensor verification passed.", level="PASS")
    sys.exit(EXIT_SUCCESS)


if __name__ == "__main__":
    main()

