import os
import subprocess
from datetime import datetime
import argparse
import json
import sys

# === USER CONFIGURATION ===
BACKUP_DIR = "/etc/config_backup"
EXTRACT_DIR = "/"
LOG_FILE = "/usr/bin/tests/config_push.log"

# === JSON PARSER ===
def parse_config(config_str):
    if config_str.startswith("CONFIGURATION="):
        config_str = config_str.split("CONFIGURATION=", 1)[1]
    try:
        return json.loads(config_str)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"Invalid CONFIGURATION JSON: {e}\n")
        sys.exit(1)

# === ARGUMENT PARSING ===
def parse_arguments():
    parser = argparse.ArgumentParser(description="Configuration Push Testcase")
    parser.add_argument('config', help="CONFIGURATION JSON string")
    return parser.parse_args()

args = parse_arguments()
config = parse_config(args.config)

MODIFIED_FILE = config.get("MODIFIED_FILE")

if not MODIFIED_FILE:
    print("❌ MODIFIED_FILE not provided in CONFIGURATION JSON")
    sys.exit(1)

# === HELPER FUNCTIONS ===
def log_step(message):
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    log_msg = f"{timestamp} {message}"
    print(log_msg)
    with open(LOG_FILE, "a") as f:
        f.write(log_msg + "\n")

def run_cmd(cmd):
    log_step(f"Executing: {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, check=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.stdout.strip():
            log_step(result.stdout.strip())
        if result.stderr.strip():
            log_step(result.stderr.strip())
    except subprocess.CalledProcessError as e:
        log_step(f"❌ Command failed: {e}")
        raise

# === MAIN TESTCASE STEPS ===
def verify_file_exists():
    log_step(f"Checking if modified configuration exists at {MODIFIED_FILE}")
    if not os.path.exists(MODIFIED_FILE):
        raise FileNotFoundError(f"❌ Modified file not found: {MODIFIED_FILE}")
    log_step("✅ Modified configuration file found.")

def backup_existing_config():
    log_step("Creating backup of existing configuration...")
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{BACKUP_DIR}/config_backup_{timestamp}.tar.gz"
    run_cmd(f"tar -czf {backup_path} /etc/config")
    log_step(f"✅ Backup created at: {backup_path}")

def apply_new_config():
    log_step("Applying new configuration from modified file...")
    run_cmd(f"tar -xzf {MODIFIED_FILE} -C {EXTRACT_DIR}")
    log_step("✅ New configuration applied successfully.")

def verify_changes():
    log_step("Verifying updated configuration files...")
    run_cmd("ls -l /etc/config")
    log_step("✅ Verification complete.")

def reboot_system():
    log_step("Rebooting the system to apply configuration...")
    print("REBOOT_TRIGGER")
    run_cmd("sleep 3 && reboot")

def main():
    log_step("=== Starting Configuration Push Testcase ===")
    try:
        verify_file_exists()
        backup_existing_config()
        apply_new_config()
        verify_changes()
        reboot_system()
    except Exception as e:
        log_step(f"❌ Test Failed: {e}")
    else:
        log_step("✅ Configuration Push Testcase completed successfully.")
    finally:
        log_step("=== Testcase Execution Finished ===")

if __name__ == "__main__":
    main()

