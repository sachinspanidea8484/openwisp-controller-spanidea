#!/usr/bin/env python3
import sys, os
from common_helper import (
    log,
    run_local_command,
    parse_configuration,
    EXIT_SUCCESS,
    EXIT_FAILED
)

EXTRACT_DIR = "/"
DEFAULT_MODIFIED_FILE = "/tmp/modified.gz"   


def verify_file_exists(path):
    log("[STEP] Checking modified file: %s", path)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Modified file not found: {path}")
    log("[PASS] Modified configuration file found.", level="PASS")


def apply_new_config(modified_file):
    log("[STEP] Applying new configuration")
    run_local_command(f"tar -xzf {modified_file} -C {EXTRACT_DIR}", allow_fail=False)
    log("[PASS] New configuration applied successfully", level="PASS")


def verify_changes():
    log("[STEP] Verifying updated configuration")
    out, _, _ = run_local_command("ls -l /etc/config", allow_fail=True) 
    if out:
        log("%s", out)
    log("[INFO] Verification complete")


def reboot_system():
    log("[STEP] Rebooting system")
    print("REBOOT_TRIGGER")  # Required for automation detection
    run_local_command("sync && reboot", allow_fail=True)  


def main():
    config = parse_configuration(sys.argv[1] if len(sys.argv) > 1 else None)
    modified_file = config.get("MODIFIED_FILE", DEFAULT_MODIFIED_FILE)

    log("=== Starting Configuration Push Testcase ===")

    try:
        verify_file_exists(modified_file)   #verify the return values for all functions
        apply_new_config(modified_file)
        verify_changes()
        reboot_system()

        log("[PASS] Configuration Push Testcase Completed Successfully", level="PASS")
        return EXIT_SUCCESS

    except Exception as e:
        log("[FAIL] Test Failed: %s", str(e), level="FAIL")
        return EXIT_FAILED


if __name__ == "__main__":
    sys.exit(main())

