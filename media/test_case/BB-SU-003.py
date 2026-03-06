# START_DESCRIPTION
# 1. Execute the command "pgrep procd" on the device.
# 2. Capture the PID of the running procd process.
# 3. Verify that the returned PID is "1".
# 4. If PID is "1", mark the test as PASSED.
# 5. If PID is not "1" or no output is returned, mark the test as FAILED.
# END_DESCRIPTION

import sys
from common_helper import log, run_local_command, EXIT_SUCCESS, EXIT_FAILED

EXPECTED_PID = "1"

def main():

    log("STEP 1: Checking if procd process is running...")

    command = "pgrep procd"

    stdout, stderr, rc = run_local_command(command, allow_fail=True)

    if stderr:
        log("ERROR: Command execution failed: %s", stderr, level="FAIL")
        sys.exit(EXIT_FAILED)

    if not stdout:
        log("FAIL: procd process not found.", level="FAIL")
        sys.exit(EXIT_FAILED)

    log("INFO: procd PID detected: %s", stdout)

    if stdout.strip() == EXPECTED_PID:
        log("PASS: procd process is running with PID 1.", level="PASS")
        sys.exit(EXIT_SUCCESS)
    else:
        log("FAIL: procd running with unexpected PID: %s", stdout, level="FAIL")
        sys.exit(EXIT_FAILED)


if __name__ == "__main__":
    main()
