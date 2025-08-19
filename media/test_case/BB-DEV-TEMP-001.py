import subprocess
import time
import re
import sys
import os

SENSOR_SCRIPT = "/usr/bin/sensor_monitor.py"
NUM_READINGS = 5
DELAY_BETWEEN_READS = 1  # second

def run_local_command(command):
    """
    Runs a shell command locally and returns stdout.
    """
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.stdout.strip()

def extract_sht4x_block(output):
    """
    Extracts the SHT4X_HWMON0 block from the sensor output.
    """
    match = re.search(
        r"SHT4X_HWMON0\s*\n(?: {2}.+\n?){2,5}",
        output
    )
    return match.group(0).strip() if match else None

def parse_temp_and_humidity(block):
    """
    Parse temperature and humidity values from the block.
    """
    temp_match = re.search(r"Temperature\s*\(°C\)\s*:\s*([\d\.\-]+)", block)
    hum_match = re.search(r"Humidity\s*\(%RH\)\s*:\s*([\d\.\-]+)", block)

    temp = float(temp_match.group(1)) if temp_match else None
    hum = float(hum_match.group(1)) if hum_match else None
    return temp, hum

def main():
    # STEP 0: Check script presence
    if not os.path.exists(SENSOR_SCRIPT):
        print(f"[ERROR] Sensor script not found at {SENSOR_SCRIPT}")
        print("[RESULT] FAILURE – Missing sensor script.")
        sys.exit(1)

    print("[STEP 1] Fetching only SHT4X_HWMON0 readings locally...\n")

    readings = []  # Store tuples (temperature, humidity)

    for i in range(1, NUM_READINGS + 1):
        output = run_local_command(f"python3 {SENSOR_SCRIPT}")
        sht4x_data = extract_sht4x_block(output)

        print(f"[{i}]")
        if sht4x_data:
            print(sht4x_data + "\n")

            temp, hum = parse_temp_and_humidity(sht4x_data)
            if temp is not None and hum is not None:
                readings.append((temp, hum))

                # Check temperature range
                if not (-45 <= temp <= 80):   
                    print(f"[{i}] [ERROR] Temperature {temp}°C out of range (-45 to 80).")
                    print("[RESULT] FAILURE – One or more SHT4X_HWMON0 checks failed.")
                    sys.exit(1)  
            else:
                print(f"[{i}] [ERROR] Could not parse Temperature/Humidity values.")
                print("[RESULT] FAILURE – One or more SHT4X_HWMON0 checks failed.")
                sys.exit(1)

        else:
            print("[ERROR] SHT4X_HWMON0 block not found.\n")
            print("[RESULT] FAILURE – One or more SHT4X_HWMON0 checks failed.")
            sys.exit(1)

        time.sleep(DELAY_BETWEEN_READS)

    # STEP 2: Identical values check (only if we collected 5 readings)
    if len(readings) == NUM_READINGS:
        if all(r == readings[0] for r in readings):
            print("[ERROR] All 5 readings are identical. Possible hard-coded values, not live sensor data.")
            print("[RESULT] FAILURE – One or more SHT4X_HWMON0 checks failed.")
            sys.exit(1)

    # Final result
    print("[RESULT] SUCCESS – All SHT4X_HWMON0 checks passed.")
    sys.exit(0)

if __name__ == "__main__":
    main()

