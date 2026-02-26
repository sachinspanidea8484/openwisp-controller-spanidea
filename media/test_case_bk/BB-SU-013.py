# START_DESCRIPTION
# 1. Perform baseline connectivity verification.
# 2. Create system configuration backup.
# 3. Apply modified configuration.
# 4. Reboot and verify system connectivity.
# 5. If connectivity fails, restore backup configuration.
# 6. Reboot system after rollback.
# 7. Verify connectivity restored successfully.
# 8. If rollback successful, mark test as PASSED.
# END_DESCRIPTION

import os
import subprocess
from datetime import datetime
import argparse
import json
import sys
import time

# ==================================================
# Integrated Rollback Test - FINAL VERSION
# ==================================================

ROOT_DIR = "/root"
LOG_FILE = "/usr/bin/tests/config_rollback_combined.log"
STATE_FILE = "/root/rollback_phase.txt"
BACKUP_PATH_FILE = "/root/rollback_backup_path.txt"

# ---------------- Logging ----------------

def log(msg):
    ts = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{ts} {msg}")
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(f"{ts} {msg}\n")

# ---------------- Command Runner ----------------

def run(cmd, allow_fail=False):
    log(f"Executing: {cmd}")
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0 and not allow_fail:
        raise RuntimeError(f"Command failed ({result.returncode}): {cmd}")
    return result.returncode

# ---------------- Interface Detection ----------------

def get_up_interfaces():
    try:
        cmd = "ip -o addr show | grep -v ' lo ' | awk '{print $2}' | sort -u"
        return subprocess.check_output(cmd, shell=True).decode().split()
    except:
        return []

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

    try:
        if os.path.exists(BACKUP_PATH_FILE):
            with open(BACKUP_PATH_FILE, "r") as f:
                backup_path = f.read().strip()

            if os.path.exists(backup_path):
                os.remove(backup_path)
                log(f"Deleted backup archive: {backup_path}")

        for f in [STATE_FILE, BACKUP_PATH_FILE]:
            if os.path.exists(f):
                os.remove(f)

        log("Cleanup complete.")
    except Exception as e:
        log(f"Cleanup error: {e}")

# ==================================================
# ================= PHASE 0 ========================
# ==================================================

def phase_initial(config):
    log("=== Phase 0: Baseline & Backup ===")

    modified_file = config.get("MODIFIED_CONFIG_FILE")
    if not modified_file or not os.path.exists(modified_file):
        log("MODIFIED_CONFIG_FILE missing.")
        sys.exit(1)

    passed_ifaces = []

    for iface in get_up_interfaces():
        if run(f"ping -I {iface} {config['PING_IP']} -c {config['PING_COUNT']}", True) == 0:
            log(f"Baseline OK: {iface}")
            passed_ifaces.append(iface)

    if not passed_ifaces:
        log("No interfaces passed baseline.")
        sys.exit(1)

    config["PASSED_INTERFACES"] = passed_ifaces

    # Create backup
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"{ROOT_DIR}/sysupgrade_backup_{ts}.tar.gz"
    run(f"sysupgrade -b {backup_file}")

    if not os.path.exists(backup_file):
        log("Backup creation failed.")
        sys.exit(1)

    with open(BACKUP_PATH_FILE, "w") as f:
        f.write(backup_file)

    log(f"Backup created: {backup_file}")

    # Apply modified config
    run(f"tar -xzf {modified_file} -C /")
    run("sync")

    with open(STATE_FILE, "w") as f:
        f.write("1")

    update_rc_local(json.dumps(config))

    log("Rebooting after config push...")
    run("reboot", True)

# ==================================================
# ================= PHASE 1 ========================
# ==================================================

def phase_after_first_reboot(config):
    log("=== Phase 1: Post-Reboot Validation ===")

    time.sleep(15)

    target_ifaces = config.get("PASSED_INTERFACES", [])
    any_fail = False

    for iface in target_ifaces:
        if run(f"ping -I {iface} {config['PING_IP']} -c {config['PING_COUNT']}", True) != 0:
            log(f"Failed after reboot: {iface}")
            any_fail = True
        else:
            log(f"Still working: {iface}")

    if not any_fail:
        print("CONFIG PUSH SUCCESS")
        full_cleanup()
        sys.exit(0)

    # -------- Rollback --------
    print("ROLLBACK TRIGGERED")
    log("Restoring backup...")

    if not os.path.exists(BACKUP_PATH_FILE):
        log("Backup path file missing.")
        sys.exit(1)

    with open(BACKUP_PATH_FILE, "r") as f:
        backup_src = f.read().strip()

    if not os.path.exists(backup_src):
        log("Backup archive missing.")
        sys.exit(1)

    with open(STATE_FILE, "w") as f:
        f.write("2")

    run(f"tar -xzf {backup_src} -C /")
    run("sync")

    log("Rebooting for rollback...")
    run("reboot", True)

# ==================================================
# ================= PHASE 2 ========================
# ==================================================

def phase_after_second_reboot(config):
    log("=== Phase 2: Final Verification ===")

    time.sleep(10)

    success = True

    for iface in config.get("PASSED_INTERFACES", []):
        if run(f"ping -I {iface} {config['PING_IP']} -c {config['PING_COUNT']}", True) != 0:
            log(f"Recovery failed: {iface}")
            success = False
        else:
            log(f"Recovery OK: {iface}")

    if success:
        log("System recovered successfully.")
    else:
        log("Recovery incomplete.")

    full_cleanup()

# ==================================================
# ================= MAIN ===========================
# ==================================================

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("config")
    args = parser.parse_args()

    raw = args.config.split("CONFIGURATION=", 1)[-1] \
        if "CONFIGURATION=" in args.config else args.config

    cfg = json.loads(raw)

    if not os.path.exists(STATE_FILE):
        phase = 0
    else:
        try:
            with open(STATE_FILE, "r") as f:
                phase = int(f.read().strip())
        except:
            phase = 0

    if phase == 0:
        phase_initial(cfg)
    elif phase == 1:
        phase_after_first_reboot(cfg)
    elif phase == 2:
        phase_after_second_reboot(cfg)



# python3 BB-SU-013.py 'CONFIGURATION={"PING_IP":"8.8.8.8","PING_COUNT":2,"MODIFIED_CONFIG_FILE":"/tmp/modified.tar.gz"}'

