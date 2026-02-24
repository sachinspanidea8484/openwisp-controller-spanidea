# START_DESCRIPTION
# 1. Verify GPS monitoring script availability.
# 2. Execute GNSS/GPS script and collect multiple readings.
# 3. Extract latitude and longitude values.
# 4. Ensure sufficient valid GPS readings are received.
# 5. Verify GPS values are not identical across samples.
# 6. If valid and dynamic readings detected, mark test as PASSED.
# END_DESCRIPTION

#!/usr/bin/env python3
import sys, os, time, select, subprocess
from common_helper import log, EXIT_SUCCESS, EXIT_FAILED

GPS_SCRIPT = "/usr/bin/gpsmon.sh"
MAX_LINES = 5


def run_command_with_limit(command, max_lines=MAX_LINES, max_time=10):
    process = subprocess.Popen(
        command, shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    out_lines, err_lines = [], []
    start = time.time()

    try:
        while True:
            ready, _, _ = select.select([process.stdout, process.stderr], [], [], 0.2)
            for stream in ready:
                line = stream.readline()
                if not line:
                    continue
                if stream == process.stdout:
                    out_lines.append(line.strip())
                else:
                    err_lines.append(line.strip())

            if len(out_lines) >= max_lines or (time.time() - start) > max_time:
                break
            if process.poll() is not None:
                break
    finally:
        process.terminate()
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            process.kill()

    return out_lines, err_lines


def verify_gps(lines):
    readings = []
    for line in lines:
        parts = line.strip().split(",")
        if len(parts) < 3:
            continue
        try:
            lat = float(parts[1])
            lon = float(parts[2])
            readings.append((lat, lon))
        except:
            continue

    if len(readings) < MAX_LINES:
        log("[FAIL] Could not collect %d valid GPS readings.", MAX_LINES, level="FAIL")
        return False

    if all(r == readings[0] for r in readings):
        log("[FAIL] All %d GPS readings identical. Possible static values.", MAX_LINES, level="FAIL")
        return False

    return True


def main():
    log("[STEP 0] Checking required GPS script...")

    if not os.path.isfile(GPS_SCRIPT):
        log("[FAIL] Required script '%s' is missing.", GPS_SCRIPT, level="FAIL")
        sys.exit(EXIT_FAILED)

    log("[STEP 1] Retrieving GNSS/GPS data...")

    out_lines, err_lines = run_command_with_limit(GPS_SCRIPT)

    if err_lines:
        log("[WARN] %s", " ".join(err_lines), level="WARN")

    log("[INFO] GNSS/GPS Output:")
    for line in out_lines:
        log("%s", line)

    log("[STEP 2] Validating GPS readings...")

    if verify_gps(out_lines):
        log("[PASS] GPS readings are valid (not identical).", level="PASS")
        log("[RESULT] SUCCESS ... GPS verification passed.", level="PASS")
        sys.exit(EXIT_SUCCESS)

    log("[RESULT] FAILURE ... GPS verification failed.", level="FAIL")
    sys.exit(EXIT_FAILED)


if __name__ == "__main__":
    main()

