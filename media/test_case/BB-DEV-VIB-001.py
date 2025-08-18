import subprocess
import sys
from datetime import datetime

def log(message):
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{timestamp} {message}")

def run_local_command(command):
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return "", str(e)

def parse_sensor_data(output):
    lines = output.strip().splitlines()
    gyro_data = {}
    accel_data = {}

    for line in lines:
        if line.startswith("Gyro:"):
            gyro_str = line.replace("Gyro:", "").strip()
            gyro_data = eval(gyro_str)  # ⚠ Trusted local output only
        elif line.startswith("Accel:"):
            accel_str = line.replace("Accel:", "").strip()
            accel_data = eval(accel_str)

    if not gyro_data or not accel_data:
        raise ValueError("Missing Gyro or Accel data")

    return gyro_data, accel_data

def verify_vibration_data():
    log("[STEP 1] Retrieving vibration/IMU sensor data locally...")

    sensor_script = "/usr/bin/read_sensor.py"
    output, error = run_local_command(f"python3 {sensor_script}")

    if error:
        log(f"[ERROR] Sensor command STDERR: {error}")

    log("[INFO] Initial Sensor Data:")
    print(output)

    try:
        gyro_data, accel_data = parse_sensor_data(output)
        log(f"[PARSED] Gyro: {gyro_data}")
        log(f"[PARSED] Accel: {accel_data}")
        log("[PASS] Sensor data retrieved and parsed successfully.")
        return True
    except Exception as e:
        log(f"[ERROR] Failed to parse sensor data: {str(e)}")
        log("[FAIL] Could not parse initial sensor data.")
        return False

if __name__ == "__main__":
    success = verify_vibration_data()
    if success:
        log("[RESULT] SUCCESS – Vibration/IMU sensor verification passed.")
        sys.exit(0)
    else:
        log("[RESULT] FAILURE – Vibration/IMU sensor verification failed.")
        sys.exit(1)

