# START_DESCRIPTION
# 1. Execute hardware reset command.
# 2. Trigger reboot detection for automation framework.
# 3. Verify reset command executed successfully.
# 4. Confirm system restarts properly.
# 5. If reset behavior is correct, mark test as PASSED.
# END_DESCRIPTION

#!/usr/bin/env python3
import sys
from common_helper import (
    log,
    run_local_command,
    EXIT_SUCCESS,
    EXIT_FAILED
)
RESET_CMD = "fpga-io -w 0x03 0x01"
def main():
    log("[STEP] Starting System Reset Verification Test")
    log("[STEP] Checking fpga-io command availability")
    out, err, rc = run_local_command("which fpga-io", allow_fail=True)
    if rc != 0:
        log("Command isn't executable", level="FAIL")
        log("System Reset Verification Test FAILED", level="FAIL")
        sys.exit(EXIT_FAILED)
    log("[STEP] Executing system reset command")
    print("REBOOT_TRIGGER")
    out, err, rc = run_local_command(RESET_CMD, allow_fail=True)
    if rc != 0:
        log("Reset command execution failed: %s", err, level="FAIL")
        log("System Reset Verification Test FAILED", level="FAIL")
        sys.exit(EXIT_FAILED)
    log("Reset command executed successfully", level="PASS")
    log("System Reset Verification Test PASSED", level="PASS")
    sys.exit(EXIT_SUCCESS)
if __name__ == "__main__":
    main()


