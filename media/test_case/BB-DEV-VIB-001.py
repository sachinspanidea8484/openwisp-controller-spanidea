import subprocess
import sys
import os
import time
from datetime import datetime

# === Config ===
SENSOR_SCRIPT = "/usr/bin/read_sensor.py"
NUM_READS = 5

# Fallback sysfs paths
GYRO_PATH = "/sys/bus/iio/devices/iio:device0"
ACCEL_PATH = "/sys/bus/iio/devices/iio:device1"


def log(message):
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{timestamp} {message}")


def run_local_command(command):
    """Run a shell command and capture stdout/stderr."""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return "", str(e)


# =====================
# Fallback IMU readers
# =====================
def read_value(path):
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except Exception:
        return "0"


def fallback_sensor_read():
    """Directly read IMU sensor from sysfs, fallback if script not found."""
    start = time.time()

    # Read gyro
    gyro_raw = {
        "x": int(read_value(f"{GYRO_PATH}/in_anglvel_x_raw")),
        "y": int(read_value(f"{GYRO_PATH}/in_anglvel_y_raw")),
        "z": int(read_value(f"{GYRO_PATH}/in_anglvel_z_raw")),
    }
    gyro_scale = float(read_value(f"{GYRO_PATH}/in_anglvel_scale"))
    gyro = {k: round(v * gyro_scale, 3) for k, v in gyro_raw.items()}

    # Read accel
    accel_raw = {
        "x": int(read_value(f"{ACCEL_PATH}/in_accel_x_raw")),
        "y": int(read_value(f"{ACCEL_PATH}/in_accel_y_raw")),
        "z": int(read_value(f"{ACCEL_PATH}/in_accel_z_raw")),
    }
    accel_scale = float(read_value(f"{ACCEL_PATH}/in_accel_scale"))
    accel = {k: round(v * accel_scale, 3) for k, v in accel_raw.items()}

    elapsed = time.time() - start

    output = f"Gyro: {gyro}\nAccel: {accel}\nRead + compute time: {elapsed:.6f} seconds"
    return output


def parse_sensor_data(output):
    lines = output.strip().splitlines()
    gyro_data = {}
    accel_data = {}

    for line in lines:
        if line.startswith("Gyro:"):
            gyro_str = line.replace("Gyro:", "").strip()
            gyro_data = eval(gyro_str)
        elif line.startswith("Accel:"):
            accel_str = line.replace("Accel:", "").strip()
            accel_data = eval(accel_str)

    if not gyro_data or not accel_data:
        raise ValueError("Missing Gyro or Accel data")

    return gyro_data, accel_data


def verify_vibration_data():
    log(f"[STEP 1] Reading vibration/IMU sensor data {NUM_READS} times...")

    readings = []

    for i in range(NUM_READS):
        # Prefer sensor script if available
        if os.path.isfile(SENSOR_SCRIPT):
            output, error = run_local_command(f"python3 {SENSOR_SCRIPT}")
            if error:
                log(f"[WARN] Sensor script error, using fallback (iteration {i+1}): {error}")
                output = fallback_sensor_read()
        else:
            output = fallback_sensor_read()

        log(f"[INFO] Raw Sensor Data (iteration {i+1}):")
        print(output)

        try:
            gyro_data, accel_data = parse_sensor_data(output)
            log(f"[PARSED] Iteration {i+1} ... Gyro: {gyro_data}, Accel: {accel_data}")
            readings.append((gyro_data, accel_data))
        except Exception as e:
            log(f"[ERROR] Iteration {i+1} failed to parse sensor data: {str(e)}")
            return False

    # STEP 2: Compare readings for variation
    first_read = readings[0]
    all_identical = all(r == first_read for r in readings)

    if all_identical:
        log("[FAIL] All vibration readings are identical ... no variation detected.")
        return False
    else:
        log("[PASS] Vibration readings show variation across samples.")
        return True


if __name__ == "__main__":
    success = verify_vibration_data()
    if success:
        log("[RESULT] SUCCESS ... Vibration/IMU sensor verification passed.")
        sys.exit(0)
    else:
        log("[RESULT] FAILURE ... Vibration/IMU sensor verification failed.")
        sys.exit(1)

