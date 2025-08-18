import subprocess
import time
import select
import sys
from datetime import datetime

EXPECTED_LATITUDE = 45.312226
EXPECTED_LONGITUDE = -68.031125
TOLERANCE = 0.0002  # Allowable variation

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
            # Wait for output with a timeout
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

    return "\n".join(output_lines), "\n".join(error_lines)

def verify_gps_output(output):
    """Verifies GPS output is within tolerance range."""
    for line in output.splitlines():
        parts = line.strip().split(",")
        if len(parts) < 3:
            continue
        try:
            lat = float(parts[1].strip())
            lon = float(parts[2].strip())
            if abs(lat - EXPECTED_LATITUDE) <= TOLERANCE and abs(lon - EXPECTED_LONGITUDE) <= TOLERANCE:
                return True
        except ValueError:
            continue
    return False

def main():
    log("[STEP 1] Retrieving GNSS/GPS data locally...")
    gps_command = "/usr/bin/gpsmon.sh"
    output, error = run_command_with_read_limit(gps_command)

    if error:
        log(f"[ERROR] {error}")

    log("[INFO] GNSS/GPS Output:")
    print(output)

    log("[STEP 2] Validating GPS position...")
    if verify_gps_output(output):
        log("[PASS] BB GNSS/GPS data matches expected position.")
        log("[RESULT] SUCCESS – GPS verification passed.")
        sys.exit(0)  # success
    else:
        log("[FAIL] BB GNSS/GPS data does NOT match expected position.")
        log("[RESULT] FAILURE – GPS verification failed.")
        sys.exit(1)  # failure

if __name__ == "__main__":
    main()

