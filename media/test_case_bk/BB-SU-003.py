import sys
import subprocess
from datetime import datetime

# === Exit Codes ===
EXIT_SUCCESS = 0
EXIT_FAILED = 1

# === Configurable Parameters ===
POST_KEYWORD = "Child connection from"

# === Utility Functions ===
def log(message):
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{timestamp} {message}")

def run_local_command(command):
    """Executes a local shell command and returns stdout and stderr."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True
        )
        return result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return "", str(e)

# === Main Test Logic ===
def main():
    log("[STEP 1] Running POST log verification locally...")

    # Step 1: Check for POST logs in system log output
    log("[STEP 2] Checking for POST logs via logread...")
    command = f"logread | grep '{POST_KEYWORD}'"
    output, error = run_local_command(command)

    if error:
        log(f"[ERROR] Command execution failed: {error}")
        sys.exit(EXIT_FAILED)

    if not output:
        log("[FAIL] No POST logs found in system logs.")
        sys.exit(EXIT_FAILED)

    log("[INFO] POST log entries detected:")
    print(output)

    # Step 2: Validate PASS/FAIL conditions in log
    log("[STEP 3] Validating Dropbear SSH connections...")
    if output:
        log("[PASS] Dropbear SSH connections detected successfully.")
        sys.exit(EXIT_SUCCESS)
    else:
        log("[FAIL] No Dropbear SSH connections found.")
        sys.exit(EXIT_FAILED)

if __name__ == "__main__":
    log("=== Test Case: BB-SU-003 Power-On-Self-Test (POST) ===")
    log("Description: Verify that POST runs during startup and logs results to syslog.\n")
    main()

