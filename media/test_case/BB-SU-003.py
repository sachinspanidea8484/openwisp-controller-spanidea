import os
import sys
import json
import time
from datetime import datetime

# Import Common Helper
from common_helper import (
    log,
    run_local_command,
    verify_file_exists,
    parse_configuration,
    EXIT_SUCCESS,
    EXIT_FAILED
)

# ==================================================
# Integrated Rollback Test - Using Common Helper
# ==================================================

ROOT_DIR = "/root"
LOG_FILE = "/usr/bin/tests/config_rollback_combined.log"
STATE_FILE = "/root/rollback_phase.txt"
BACKUP_PATH_FILE = "/root/rollback_backup_path.txt"


# ---------------- Interface Detection ----------------

def get_up_interfaces():
    cmd = "ip -o addr show | grep -v ' lo ' | awk '{print $2}' | sort -u"
    out, err, rc = run_local_command(cmd, allow_fail=True)
    if rc != 0:
        return []
    return out.split()


# ---------------- rc.local Handling ----------------

def update_rc_local(config_str):
    script_path = os.path.abspath(__file__)
    exec_line = f"python3 {script_path} 'CONFIGURATION={config_str}'"

    if not os.path.exists("/etc/rc.local"):
        with open("/etc/rc.local", "w") as f:
            f.write("#!/bin/sh -e\nexit 0\n")

    with open("/etc/rc.local", "r") as f:
        lines = f.readlines()

    if any(script_path in line for line in lines):
        return

    with open("/etc/rc.local", "w") as f:
        for line in lines:
            if line.strip() == "exit 0":
                f.write(f"{exec_line}\n")
            f.write(line)


def clear_rc_local():
    script_path = os.path.abspath(__file__)
    if not os.path.exists("/etc/rc.local"):
        return

    with open("/etc/rc.local", "r") as f:
        lines = f.readlines()

    with open("/etc/rc.local", "w") as f:
        for line in lines:
            if script_path not in line:
                f.write(line)


# ---------------- Cleanup ----------------

def full_cleanup():
    log("Starting cleanup...")

    clear_rc_local()

    if os.path.exists(BACKUP_PATH_FILE):
        with open(BACKUP_PATH_FILE, "r") as f:
            backup_path = f.read().strip()

        if os.path.exists(backup_path):
            os.remove(backup_path)
            log("Deleted backup archive: %s", backup_path)

    for f in [STATE_FILE, BACKUP_PATH_FILE]:
        if os.path.exists(f):
            os.remove(f)

    log("Cleanup complete.")


# ==================================================
# ================= PHASE 0 ========================
# ==================================================

def phase_initial(config):
    log("=== Phase 0: Baseline & Backup ===")

    modified_file = config.get("MODIFIED_CONFIG_FILE")

    if not verify_file_exists(modified_file):
        sys.exit(EXIT_FAILED)

    passed_ifaces = []

    for iface in get_up_interfaces():
        cmd = f"ping -I {iface} {config['PING_IP']} -c {config['PING_COUNT']}"
        _, _, rc = run_local_command(cmd, allow_fail=True)

        if rc == 0:
            log("Baseline OK: %s", iface)
            passed_ifaces.append(iface)

    if not passed_ifaces:
        log("No interfaces passed baseline.", level="FAIL")
        sys.exit(EXIT_FAILED)

    config["PASSED_INTERFACES"] = passed_ifaces

    # -------- Backup --------
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"{ROOT_DIR}/sysupgrade_backup_{ts}.tar.gz"

    _, _, rc = run_local_command(f"sysupgrade -b {backup_file}")
    if rc != 0 or not os.path.exists(backup_file):
        log("Backup creation failed.", level="FAIL")
        sys.exit(EXIT_FAILED)

    with open(BACKUP_PATH_FILE, "w") as f:
        f.write(backup_file)

    log("Backup created: %s", backup_file)

    # -------- Apply Modified Config --------
    run_local_command(f"tar -xzf {modified_file} -C /")
    run_local_command("sync")

    with open(STATE_FILE, "w") as f:
        f.write("1")
    print("REBOOT_TRIGGER")  # Required for automation detection
    update_rc_local(json.dumps(config))

    log("Rebooting after config push...")
    run_local_command("reboot", allow_fail=True)


# ==================================================
# ================= PHASE 1 ========================
# ==================================================

def phase_after_first_reboot(config):
    log("=== Phase 1: Post-Reboot Validation ===")

    time.sleep(15)

    any_fail = False

    for iface in config.get("PASSED_INTERFACES", []):
        cmd = f"ping -I {iface} {config['PING_IP']} -c {config['PING_COUNT']}"
        _, _, rc = run_local_command(cmd, allow_fail=True)

        if rc != 0:
            log("Failed after reboot: %s", iface, level="FAIL")
            any_fail = True
        else:
            log("Still working: %s", iface, level="PASS")

    if not any_fail:
        log("CONFIG PUSH SUCCESS", level="PASS")
        full_cleanup()
        sys.exit(EXIT_SUCCESS)

    # -------- Rollback --------
    log("ROLLBACK TRIGGERED")

    if not verify_file_exists(BACKUP_PATH_FILE):
        sys.exit(EXIT_FAILED)

    with open(BACKUP_PATH_FILE, "r") as f:
        backup_src = f.read().strip()

    if not verify_file_exists(backup_src):
        sys.exit(EXIT_FAILED)

    with open(STATE_FILE, "w") as f:
        f.write("2")

    run_local_command(f"tar -xzf {backup_src} -C /")
    run_local_command("sync")

    log("Rebooting for rollback...")
    run_local_command("reboot", allow_fail=True)


# ==================================================
# ================= PHASE 2 ========================
# ==================================================

def phase_after_second_reboot(config):
    log("=== Phase 2: Final Verification ===")

    time.sleep(10)

    success = True

    for iface in config.get("PASSED_INTERFACES", []):
        cmd = f"ping -I {iface} {config['PING_IP']} -c {config['PING_COUNT']}"
        _, _, rc = run_local_command(cmd, allow_fail=True)

        if rc != 0:
            log("Recovery failed: %s", iface, level="FAIL")
            success = False
        else:
            log("Recovery OK: %s", iface, level="PASS")

    if success:
        log("System recovered successfully.", level="PASS")
    else:
        log("Recovery incomplete.", level="FAIL")

    full_cleanup()

    sys.exit(EXIT_SUCCESS if success else EXIT_FAILED)


# ==================================================
# ================= MAIN ===========================
# ==================================================

if __name__ == "__main__":

    if len(sys.argv) < 2:
        log("CONFIGURATION argument missing", level="FAIL")
        sys.exit(EXIT_FAILED)

    config = parse_configuration(sys.argv[1])

    if not os.path.exists(STATE_FILE):
        phase = 0
    else:
        try:
            with open(STATE_FILE, "r") as f:
                phase = int(f.read().strip())
        except:
            phase = 0

    if phase == 0:
        phase_initial(config)
    elif phase == 1:
        phase_after_first_reboot(config)
    elif phase == 2:
        phase_after_second_reboot(config)

