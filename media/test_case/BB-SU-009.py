#!/usr/bin/env python3
import sys, time
from common_helper import (
    log,
    run_local_command,
    parse_configuration,
    EXIT_SUCCESS,
    EXIT_FAILED
)


def run_cmd(cmd, desc):
    log("[STEP] %s", desc)
    out, err, rc = run_local_command(cmd, allow_fail=True)

    if rc != 0:
        log("[FAIL] Command failed: %s", cmd, level="FAIL")
        if err:
            log("[ERROR] %s", err, level="FAIL")
        raise Exception("Command execution failed")

    if out:
        log("[INFO] %s", out)
    if err:
        log("[WARN] %s", err, level="WARN")


def wait_sec(sec, desc):
    log("[STEP] %s (%ds)", desc, sec)
    for i in range(sec):
        log("[INFO] Waiting... %d/%d seconds", i + 1, sec)
        time.sleep(1)


def main():
    config = parse_configuration(sys.argv[1] if len(sys.argv) > 1 else None)

    timeout = config.get("timeout")
    if not timeout:
        log("[FAIL] Missing 'timeout' in CONFIGURATION", level="FAIL")
        return EXIT_FAILED

    log("WATCHDOG TEST STARTED (Timeout=%ds)", timeout)

    try:
        # ===== CYCLE 1 =====
        run_cmd("ubus call system watchdog", "Check Status")
        run_cmd("ubus call system watchdog '{\"magicclose\": true}'", "Disable Watchdog")
        run_cmd(f"ubus call system watchdog '{{\"timeout\":{timeout}}}'", "Set Timeout")
        run_cmd("ubus call system watchdog '{\"stop\":true}'", "Stop Feed (Cycle 1)")
        wait_sec(timeout + 2, "Waiting Cycle 1")

        log("[INFO] Device NOT rebooted (watchdog disabled)")

        # ===== CYCLE 2 =====
        log("SECOND CYCLE")
        run_cmd("ubus call system watchdog '{\"stop\":false}'", "Resume Feed")
        run_cmd("ubus call system watchdog '{\"magicclose\": false}'", "Enable Watchdog")
        run_cmd(f"ubus call system watchdog '{{\"timeout\":{timeout}}}'", "Reset Timeout")

        print("REBOOT_TRIGGER")  # Required for automation detection

        run_cmd("ubus call system watchdog '{\"stop\":true}'", "Stop Feed (Cycle 2)")

        log("[PASS] Watchdog reboot triggered successfully", level="PASS")
        return EXIT_SUCCESS

    except Exception as e:
        log("[FAIL] Test execution failed: %s", str(e), level="FAIL")
        return EXIT_FAILED


if __name__ == "__main__":
    sys.exit(main())


#python3 BB-SU-006.py CONFIGURATION='{"timeout":15}'
