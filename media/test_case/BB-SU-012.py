import os
import time
import subprocess
from datetime import datetime
import argparse

# === USER CONFIGURATION ===
BACKUP_DIR = "/etc/config_backup"
EXTRACT_DIR = "/"
LOG_FILE = "/usr/bin/tests/config_push.log"

# === ARGUMENT PARSING ===
def parse_arguments():
    parser = argparse.ArgumentParser(description="Configuration Push Testcase")
    parser.add_argument('-m', '--modified-file', required=True,
                        help="Path to the modified tarball file to apply")
    return parser.parse_args()

args = parse_arguments()
MODIFIED_FILE = args.modified_file

# === HELPER FUNCTIONS ===
def log_step(message):
    """Log messages with timestamps."""
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    log_msg = f"{timestamp} {message}"
    print(log_msg)
    with open(LOG_FILE, "a") as f:
        f.write(log_msg + "\n")

def run_cmd(cmd):
    """Run shell command and log output."""
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
    """Ensure the modified configuration file is available."""
    log_step(f"Checking if modified configuration exists at {MODIFIED_FILE}")
    if not os.path.exists(MODIFIED_FILE):
        raise FileNotFoundError(f"❌ Modified file not found: {MODIFIED_FILE}")
    else:
        log_step("✅ Modified configuration file found.")

def backup_existing_config():
    """Backup current configuration."""
    log_step("Creating backup of existing configuration...")
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{BACKUP_DIR}/config_backup_{timestamp}.tar.gz"
    run_cmd(f"tar -czf {backup_path} /etc/config")
    log_step(f"✅ Backup created at: {backup_path}")

def apply_new_config():
    """Extract and apply the modified configuration."""
    log_step("Applying new configuration from modified file...")
    run_cmd(f"tar -xzf {MODIFIED_FILE} -C {EXTRACT_DIR}")
    log_step("✅ New configuration applied successfully.")

def verify_changes():
    """Check configuration directory for updates."""
    log_step("Verifying updated configuration files...")
    run_cmd("ls -l /etc/config")
    log_step("✅ Verification complete.")

def reboot_system():
    """Reboot the system to apply configuration."""
    log_step("Rebooting the system to apply configuration...")
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


