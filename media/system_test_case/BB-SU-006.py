#!/usr/bin/env python3
import os
import sys
import json
import argparse
import subprocess
from datetime import datetime

def log(message):
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{timestamp} {message}")

def parse_configuration(config_str):
    if config_str.startswith("CONFIGURATION="):
        config_str = config_str[len("CONFIGURATION="):]
    try:
        return json.loads(config_str)
    except json.JSONDecodeError as e:
        print(f"Error parsing CONFIGURATION JSON: {e}", file=sys.stderr)
        sys.exit(1)

def get_installed_modems():
    modems_found = []
    try:
        output = subprocess.check_output("lsusb", shell=True, text=True)
        for line in output.splitlines():
            if any(k in line.lower() for k in ["telit","quectel","fibocom","sierra","huawei","simcom"]):
                model = line.split(":")[-1].strip()
                modems_found.append(model)
    except:
        pass
    return modems_found

def get_wifi_interfaces():
    wifi_list = []
    try:
        output = subprocess.check_output("iwinfo | grep Hardware", shell=True, text=True)
        for line in output.splitlines():
            iface = line.split()[0].strip()
            wifi_list.append(iface)
    except:
        pass
    return wifi_list

def main():
    parser = argparse.ArgumentParser(description="BB-SU-006 Modem & Wi-Fi Interface Verification Test")
    parser.add_argument("config", help="CONFIGURATION='{\"expected_modems\":0,\"expected_wifi\":1}'")
    args = parser.parse_args()

    config = parse_configuration(args.config)

    EXPECTED_MODEMS = config.get("expected_modems")
    EXPECTED_WIFI = config.get("expected_wifi")

    if EXPECTED_MODEMS is None or EXPECTED_WIFI is None:
        log("[FAIL] Missing expected_modems or expected_wifi in CONFIGURATION JSON.")
        sys.exit(1)

    log("[STEP 1] Starting Modem and Wi-Fi Interface Verification Test")

    modems_found = get_installed_modems()
    wifi_found = get_wifi_interfaces()

    actual_settings = {
        "expected_modems": len(modems_found),
        "expected_wifi": len(wifi_found)
    }

    log(f"[INFO] Detected Modems ({len(modems_found)}): {modems_found or 'None'}")
    log(f"[INFO] Detected Wi-Fi Interfaces ({len(wifi_found)}): {wifi_found or 'None'}")

    # === EXACT SAME VALIDATION BEHAVIOR AS BB-SU-004 ===
    test_passed = True

    for key, expected_value in config.items():
        actual_value = actual_settings.get(key)

        if actual_value == expected_value:
            log(f"[PASS] Config '{key}' matches expected value '{expected_value}'")
        else:
            log(f"[FAIL] Config '{key}' expected '{expected_value}' but found '{actual_value}'")
            test_passed = False

    if test_passed:
        log("[PASS] All expected hardware counts verified successfully.")
        log("[PASS] Test Case PASSED.")
    else:
        log("[FAIL] Test Case FAILED.")
        sys.exit(1)

if __name__ == "__main__":
    main()

