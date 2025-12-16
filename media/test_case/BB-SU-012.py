#!/usr/bin/env python3

import os
import subprocess
from datetime import datetime
import argparse
import json
import sys

# === EXIT CODES ===
EXIT_SUCCESS = 0
EXIT_FAILED = 1

BACKUP_DIR = "/etc/config_backup"
EXTRACT_DIR = "/"
LOG_FILE = "/usr/bin/tests/config_push.log"
DEFAULT_MODIFIED_FILE = "/tmp/modified.gz"



def parse_config(config_str):
    if config_str.startswith("CONFIGURATION="):
        config_str = config_str[len("CONFIGURATION="):]

    try:
        return json.loads(config_str)
    except json.JSONDecodeError as e:
        print(f"Error parsing CONFIGURATION JSON: {e}", file=sys.stderr)
        return {}


def log_step(message):
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    log_msg = f"{timestamp} {message}"
    print(log_msg)
    with open(LOG_FILE, "a") as f:
        f.write(log_msg + "\n")


def run_cmd(cmd):
    log_step(f"Executing Command: {cmd}")
    try:
        result = subprocess.run(
            cmd, shell=True, check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if result.stdout.strip():
            log_step(result.stdout.strip())
        if result.stderr.strip():
            log_step(result.stderr.strip())
    except subprocess.CalledProcessError as e:
        log_step(f"Command failed: {e}")
        raise


def verify_file_exists(modified_file):
    log_step(f"Checking if modified file exists at {modified_file}")
    if not os.path.exists(modified_file):
        raise FileNotFoundError(f"Modified file not found: {modified_file}")
    log_step("Modified configuration file found.")


def backup_existing_config():
    log_step("Creating configuration backup...")
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{BACKUP_DIR}/config_backup_{timestamp}.tar.gz"
    run_cmd(f"tar -czf {backup_path} /etc/config")
    log_step(f"Backup created at: {backup_path}")


def apply_new_config(modified_file):
    log_step("Applying new configuration...")
    run_cmd(f"tar -xzf {modified_file} -C {EXTRACT_DIR}")
    log_step("New configuration applied successfully.")


def verify_changes():
    log_step("Verifying updated configuration...")
    run_cmd("ls -l /etc/config")
    log_step("Verification complete.")


def reboot_system():
    log_step("Rebooting system...")
    print("REBOOT_TRIGGER")
    run_cmd("sleep 3 && reboot")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Configuration Push Testcase")
    parser.add_argument("config", help="CONFIGURATION='{\"MODIFIED_FILE\":\"path\"}'")
    args = parser.parse_args()

    config = parse_config(args.config)
    MODIFIED_FILE = config.get("MODIFIED_FILE", DEFAULT_MODIFIED_FILE)

    log_step("=== Starting Configuration Push Testcase ===")

    try:
        verify_file_exists(MODIFIED_FILE)
        backup_existing_config()
        apply_new_config(MODIFIED_FILE)
        verify_changes()
        reboot_system()

        log_step("=== Testcase Execution Finished Successfully ===")
        sys.exit(EXIT_SUCCESS)

    except Exception as e:
        log_step(f"Test Failed: {e}")
        log_step("=== Testcase Execution Finished With Errors ===")
        sys.exit(EXIT_FAILED)
