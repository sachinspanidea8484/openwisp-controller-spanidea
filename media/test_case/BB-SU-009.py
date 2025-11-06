import os
import time
import subprocess
import logging
from datetime import datetime

# === Logging Configuration ===
logging.basicConfig(
    filename="/tmp/watchdog_test.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger().addHandler(console)

def run_cmd(cmd, desc):
    """Run a shell command and log output"""
    logging.info(f"=== {desc} ===")
    try:
        result = subprocess.run(cmd, shell=True, check=True, text=True, capture_output=True)
        logging.info(result.stdout.strip())
        if result.stderr:
            logging.warning(result.stderr.strip())
    except subprocess.CalledProcessError as e:
        logging.error(f"Command failed: {e}")
        logging.error(e.stderr.strip())

def main():
    logging.info("=== Watchdog Timer Test Started ===")

    # Step 1: Confirm Watchdog Is Enabled
    run_cmd("ubus call system watchdog", "Checking watchdog status")

    # Step 2: Set the Watchdog Timeout (10 seconds)
    run_cmd("ubus call system watchdog '{\"timeout\":10}'", "Setting watchdog timeout to 10 seconds")

    # Step 3: Simulate System Hang (Stop Feeding Watchdog)
    run_cmd("ubus call system watchdog '{\"stop\":true}'", "Stopping watchdog feed to simulate system hang")

    # Step 4: Wait for reboot (no feeding)
    logging.info("System will reboot automatically after timeout (~10s). Waiting...")
    for i in range(10):
        logging.info(f"Waiting... {i+1}/10 seconds")
        time.sleep(1)

    # Step 5: If system didn't reboot (for debugging)
    logging.warning("If you see this message, watchdog did not trigger a reboot as expected.")

if __name__ == "__main__":
    main()

