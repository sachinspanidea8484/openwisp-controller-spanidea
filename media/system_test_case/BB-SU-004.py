#!/usr/bin/env python3
import os
import sys
import json
import argparse
from datetime import datetime

# Mapping keys to UCI config files
CONFIG_FILES = {
    "hostname": "/etc/config/system",
    "network_mode": "/etc/config/network",
    "wifi_enabled": "/etc/config/wireless"
}

# === Utility Functions ===
def log(message):
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{timestamp} {message}")

def verify_file_exists(filepath):
    if not os.path.isfile(filepath):
        log(f"[FAIL] Configuration file not found: {filepath}")
        return False
    log(f"[PASS] Verified configuration file exists: {filepath}")
    return True

def read_uci_config(filepath):
    """Read UCI-style config and return key-value dict."""
    config = {}
    if not os.path.isfile(filepath):
        return config
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("config") or line.startswith("section"):
                continue
            if line.startswith("option"):
                parts = line.split(None, 3)
                if len(parts) >= 3:
                    _, key, value = parts[0:3]
                    config[key.strip()] = value.strip().strip("'\"")
    return config

def parse_configuration(config_str):
    """Parse CONFIGURATION=... JSON passed via CLI."""
    if config_str.startswith("CONFIGURATION="):
        config_str = config_str[len("CONFIGURATION="):]
    try:
        return json.loads(config_str)
    except json.JSONDecodeError as e:
        print(f"Error parsing CONFIGURATION JSON: {e}", file=sys.stderr)
        sys.exit(1)

# === Main Test ===
def main():

    parser = argparse.ArgumentParser(description="BB-SU-004 Initial Default Configuration Test")
    parser.add_argument("config", help="CONFIGURATION='{\"hostname\":\"NXP\",...}'")

    args = parser.parse_args()

    # Parse CLI JSON input
    EXPECTED_SETTINGS = parse_configuration(args.config)

    log("[STEP 1] Starting Initial/Default Configuration Test")

    actual_settings = {}

    # Hostname
    cfg_file = CONFIG_FILES["hostname"]
    log(f"[STEP 2] Reading configuration: {cfg_file}")
    if verify_file_exists(cfg_file):
        system_cfg = read_uci_config(cfg_file)
        actual_settings["hostname"] = system_cfg.get("hostname")

    # Network mode
    cfg_file = CONFIG_FILES["network_mode"]
    log(f"[STEP 2] Reading configuration: {cfg_file}")
    if verify_file_exists(cfg_file):
        network_cfg = read_uci_config(cfg_file)
        actual_settings["network_mode"] = network_cfg.get("proto")

    # WiFi enabled
    cfg_file = CONFIG_FILES["wifi_enabled"]
    log(f"[STEP 2] Reading configuration: {cfg_file}")
    if verify_file_exists(cfg_file):
        wireless_cfg = read_uci_config(cfg_file)
        disabled = wireless_cfg.get("disabled")
        if disabled == "0":
            actual_settings["wifi_enabled"] = "yes"
        elif disabled == "1":
            actual_settings["wifi_enabled"] = "no"
        else:
            actual_settings["wifi_enabled"] = None

    # Admin user always "root"
    actual_settings["admin_user"] = "root"

    # Step 3: Validate
    log("[STEP 3] Validating configuration values...")
    test_passed = True
    for key, expected_value in EXPECTED_SETTINGS.items():
        actual_value = actual_settings.get(key)
        if actual_value == expected_value:
            log(f"[PASS] Config '{key}' matches expected value '{expected_value}'")
        else:
            log(f"[FAIL] Config '{key}' expected '{expected_value}' but found '{actual_value}'")
            test_passed = False

    if test_passed:
        log("[PASS] Initial/default configuration is correct")
    else:
        log("[FAIL] Initial/default configuration does not match expected values")
        sys.exit(1)

if __name__ == "__main__":
    main()

