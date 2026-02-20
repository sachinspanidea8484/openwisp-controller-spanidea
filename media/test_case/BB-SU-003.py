

import sys
from common_helper import log, run_local_command

# === Configurable Parameters ===
POST_KEYWORD = "Child connection from"

# === Utility Functions ===
def main():
    log("STEP 1: Running POST log verification locally...")

    # Step 1: Check for POST logs in system log output
    log("STEP 2: Checking for POST logs via logread...")   #run it in MQTT
    command = f"logread -e '{POST_KEYWORD}'"
    
    # FIXED: Handle 3 values with 2-value unpacking style
    result = run_local_command(command, allow_fail=True)
    stdout = result[0] if result else ""
    stderr = result[1] if len(result) > 1 else ""
    
    if stderr:
        log(f"ERROR: Command execution failed: {stderr}")
        sys.exit(1)

    if not stdout:
        log("FAIL: No POST logs found in system logs.")
        sys.exit(1)

    log("INFO: POST log entries detected:")
    print(stdout)

    # Step 2: Validate PASS/FAIL conditions in log
    log("PASS: Dropbear SSH connections detected successfully.")
    sys.exit(0)

if __name__ == "__main__":
    main()

