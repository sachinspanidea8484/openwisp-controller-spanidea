import subprocess
import time
import re
import sys

SENSOR_SCRIPT = "/usr/bin/sensor_monitor.py"
NUM_READINGS = 5
DELAY_BETWEEN_READS = 2  # seconds

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

def main():
    print("[STEP 1] Fetching only SHT4X_HWMON0 readings locally...\n")

    all_success = True  # Track if all readings succeed

    for i in range(1, NUM_READINGS + 1):
        output = run_local_command(f"python3 {SENSOR_SCRIPT}")
        sht4x_data = extract_sht4x_block(output)

        print(f"[{i}]")
        if sht4x_data:
            print(sht4x_data + "\n")
        else:
            print("[ERROR] SHT4X_HWMON0 block not found.\n")
            all_success = False  # Mark as failure if any reading is missing

        time.sleep(DELAY_BETWEEN_READS)

    # Final result
    if all_success:
        print("[RESULT] SUCCESS – All readings contained SHT4X_HWMON0 block.")
        sys.exit(0)
    else:
        print("[RESULT] FAILURE – One or more readings missing SHT4X_HWMON0 block.")
        sys.exit(1)

if __name__ == "__main__":
    main()

