import time
import subprocess
from datetime import datetime

LOG_FILE = "/tmp/watchdog_test.log"

def log(message):
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    msg = f"{timestamp} {message}"
    print(msg)
    with open(LOG_FILE, "a") as f:
        f.write(msg + "\n")

def run_cmd(cmd, desc):
    log(f"[STEP] {desc}")
    try:
        result = subprocess.run(cmd, shell=True, check=True, text=True, capture_output=True)
        if result.stdout.strip():
            log(f"[INFO] {result.stdout.strip()}")
        if result.stderr.strip():
            log(f"[WARN] {result.stderr.strip()}")
    except subprocess.CalledProcessError as e:
        log(f"[FAIL] Command execution failed")
        if e.stderr:
            log(f"[ERROR] {e.stderr.strip()}")

def wait_sec(seconds, desc):
    log(f"[STEP] {desc} ({seconds}s)")
    for i in range(seconds):
        log(f"[INFO] Waiting... {i+1}/{seconds} seconds")
        time.sleep(1)

def main():
    log("WATCHDOG TEST STARTED")

    # -------- CYCLE 1 --------
    run_cmd("ubus call system watchdog", "Check Status")
    run_cmd("ubus call system watchdog '{\"magicclose\": true}'", "Magic Close (Disable Watchdog)")
    run_cmd("ubus call system watchdog '{\"timeout\":10}'", "Set Timeout 10s")
    run_cmd("ubus call system watchdog '{\"stop\":true}'", "Stop Feed (Cycle 1)")
    wait_sec(10, "Waiting Cycle 1")

    # ✅ Added Message After First Cycle
    log("[INFO] Device is NOT rebooted because watchdog is disabled (magicclose enabled)")

    # -------- CYCLE 2 --------
    log("SECOND CYCLE")
    run_cmd("ubus call system watchdog '{\"stop\":false}'", "Resume Feed")
    run_cmd("ubus call system watchdog '{\"magicclose\": false}'", "Enable Watchdog")
    run_cmd("ubus call system watchdog '{\"timeout\":10}'", "Reset Timeout")
    run_cmd("ubus call system watchdog '{\"stop\":true}'", "Stop Feed (Cycle 2)")
    
    wait_sec(15, "Waiting Reboot")

    log("[FAIL] Watchdog did NOT reboot device")

if __name__ == "__main__":
    main()

