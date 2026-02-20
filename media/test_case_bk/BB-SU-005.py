#!/usr/bin/env python3
import os
import sys
import json
import argparse
from datetime import datetime

VERSION_PATHS = [
    "/etc/version",
    "/etc/os-release",
    "/usr/lib/os-release"
]

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

def extract_version_from_file(path):
    try:
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                if any(k in line for k in ["VERSION_ID", "VERSION", "version"]):
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        return parts[1].strip().strip('"\'')
                    else:
                        return line.strip()
        return None
    except:
        return None

def get_software_version():
    for path in VERSION_PATHS:
        if os.path.isfile(path):
            log(f"[INFO] Found version file: {path}")
            ver = extract_version_from_file(path)
            if ver:
                return ver
    return None

def main():
    parser = argparse.ArgumentParser(description="BB-SU-005 Software Version Verification Test")
    parser.add_argument("config", help="CONFIGURATION='{\"expected_version\":\"24.10-SNAPSHOT\"}'")
    args = parser.parse_args()

    config = parse_configuration(args.config)

    EXPECTED_VERSION = config.get("expected_version")
    if EXPECTED_VERSION is None:
        log("[FAIL] Missing 'expected_version' in CONFIGURATION JSON.")
        sys.exit(1)

    log("[STEP 1] Starting Software Version Verification Test")

    # === Actual System Values ===
    current_version = get_software_version()
    actual_settings = {"expected_version": current_version}

    if not current_version:
        log("[FAIL] Unable to retrieve current software version from system.")
        sys.exit(1)

    log(f"[INFO] Retrieved Software Version: {current_version}")
    log(f"[INFO] Expected Software Version: {EXPECTED_VERSION}")

    # === VALIDATION (same as BB-SU-004) ===
    test_passed = True

    for key, expected_value in config.items():
        actual_value = actual_settings.get(key)

        if actual_value == expected_value:
            log(f"[PASS] Config '{key}' matches expected value '{expected_value}'")
        else:
            log(f"[FAIL] Config '{key}' expected '{expected_value}' but found '{actual_value}'")
            test_passed = False

    if test_passed:
        log("[PASS] Software image version matches the expected version.")
        log("[PASS] Test Case PASSED.")
    else:
        log("[FAIL] Test Case FAILED.")
        sys.exit(1)

if __name__ == "__main__":
    main()

