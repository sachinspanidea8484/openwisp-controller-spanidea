import os
import subprocess
import time
import select
import sys
from datetime import datetime

GPS_SCRIPT = "/usr/bin/gpsmon.sh"

def log(message):
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{timestamp} {message}")

def run_command_with_read_limit(command, max_lines=5, max_time=10):
    """Runs a local command, reads up to max_lines or until max_time seconds without blocking."""
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    output_lines = []
    error_lines = []
    start_time = time.time()

    try:
        while True:
            ready, _, _ = select.select([process.stdout, process.stderr], [], [], 0.2)

            for stream in ready:
                line = stream.readline()
                if not line:
                    continue
                if stream == process.stdout:
                    output_lines.append(line.strip())
                elif stream == process.stderr:
                    error_lines.append(line.strip())

            if len(output_lines) >= max_lines or (time.time() - start_time) > max_time:
                break

            if process.poll() is not None:
                break
    finally:
        process.terminate()
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            process.kill()

    return output_lines, error_lines

def check_file_presence(file_path):
    """Check if required script exists."""
    if not os.path.isfile(file_path):
        log(f"[FAIL] Required script '{file_path}' is missing. Test failed.")
        sys.exit(1)
    else:
        log(f"[INFO] Found required script: {file_path}")

def verify_gps_output(lines):
    """Verify 5 GPS readings: collected & not identical."""
    readings = []
    for line in lines:
        parts = line.strip().split(",")
        if len(parts) < 3:
            continue
        try:
            lat = float(parts[1].strip())
            lon = float(parts[2].strip())
            readings.append((lat, lon))
        except ValueError:
            continue

    if len(readings) < 5:
        log("[FAIL] Could not collect 5 valid GPS readings.")
        return False

    # Check for identical readings
    if all(r == readings[0] for r in readings):
        log("[FAIL] All 5 GPS readings are identical. Possible hardcoded/static values.")
        return False

    return True

def main():
    log("[STEP 0] Checking required GPS script file...")
    check_file_presence(GPS_SCRIPT)

    log("[STEP 1] Retrieving GNSS/GPS data locally...")
    output_lines, error_lines = run_command_with_read_limit(GPS_SCRIPT, max_lines=5, max_time=10)

    if error_lines:
        log(f"[ERROR] {''.join(error_lines)}")

    log("[INFO] GNSS/GPS Output:")
    for line in output_lines:
        print(line)

    log("[STEP 2] Validating GPS readings...")
    if verify_gps_output(output_lines):
        log("[PASS] BB GNSS/GPS data readings are valid (not identical).")
        log("[RESULT] SUCCESS – GPS verification passed.")
        sys.exit(0)
    else:
        log("[RESULT] FAILURE – GPS verification failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()

