#!/usr/bin/env python3
import sys
import argparse

from common_helper import (
    log,
    run_local_command,
    parse_configuration,
    EXIT_SUCCESS,
    EXIT_FAILED
)

def get_uci_value(command, key_suffix):
    stdout, _, rc = `run_local_command(command, allow_fail=True) #stdout → command output, rc → return code, _ → ignores stder
    if rc != 0 or not stdout:
        return None

    for line in stdout.splitlines():
        if "=" not in line:     #skip the key=value format
            continue
        key, value = line.split("=", 1) #should be one line
        if key.endswith(key_suffix):
            return value.strip().strip("'\"")

    return None


def get_all_network_protos():
    stdout, _, rc = run_local_command("uci show network", allow_fail=True) #stdout → command output, rc → return code, _ → ignores stder

    if rc != 0 or not stdout:
        return []

    protos = []
    for line in stdout.splitlines():
        if ".proto=" in line:
            _, value = line.split("=", 1)
            protos.append(value.strip().strip("'\""))

    return protos


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "config",
        help="CONFIGURATION='{\"hostname\":\"OPENWRT\",...}'"
    )
    args = parser.parse_args()
    expected_settings = parse_configuration(args.config)
    log("[STEP 1] Starting Initial / Default Configuration Test")
    actual_settings = {}

    # Hostname
    actual_settings["hostname"] = get_uci_value("uci show system",
        ".hostname"
    )
    # Network mode (ANY proto match)
    expected_proto = expected_settings.get("network_mode")
    all_protos = get_all_network_protos()
    actual_settings["network_mode"] = (
        expected_proto if expected_proto in all_protos else all_protos[0] if all_protos else None   
    )   #need to test with DCHP & Need to do review above if block

    # WiFi enabled
    disabled = get_uci_value(
        "uci show wireless",
        ".disabled"
    )
    if disabled == "0":
        actual_settings["wifi_enabled"] = "yes"
    elif disabled == "1":
        actual_settings["wifi_enabled"] = "no"
    else:
        actual_settings["wifi_enabled"] = None

    # Admin user
    actual_settings["admin_user"] = "root"  #need to check all posible usernames

    # Validation
    log("[STEP 2] Validating configuration values")
    test_passed = True

    for key, expected_value in expected_settings.items():
        actual_value = actual_settings.get(key)

        if actual_value == expected_value:
            log(
                "Config '%s' matches expected value '%s'",
                key,
                expected_value,
                level="PASS"
            )
        else:
            log(
                "Config '%s' expected '%s' but found '%s'",
                key,
                expected_value,
                actual_value,
                level="FAIL"
            )
            test_passed = False

    if test_passed:
        log("Initial / default configuration is correct", level="PASS")
        log("Test Case PASSED", level="PASS")
        return EXIT_SUCCESS
    else:
        log("Initial / default configuration does not match expected values", level="FAIL")
        log("Test Case FAILED", level="FAIL")
        return EXIT_FAILED


if __name__ == "__main__":
    main()


# python3 BB-SU-004.py CONFIGURATION='{"admin_user": "root","hostname": "Nokia","network_mode": "gre","wifi_enabled": "no"}'

#need to print expected values, if given value is not

