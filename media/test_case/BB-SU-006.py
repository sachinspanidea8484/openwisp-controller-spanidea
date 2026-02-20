#!/usr/bin/env python3
import sys
import argparse
from common_helper import log, run_local_command, parse_configuration, EXIT_SUCCESS, EXIT_FAILED

# Known cellular modem vendor keywords (used to identify USB modems)
MODEM_KEYWORDS = ["telit", "quectel", "fibocom", "sierra", "huawei", "simcom"]


def get_installed_modems():
    """
    Detect connected USB cellular modems using 'lsusb'.
    Returns a list of matching modem description lines.
    """
    stdout, _, rc = run_local_command("lsusb", allow_fail=True)

    # If command failed or no output → no modems detected
    if rc != 0 or not stdout:
        return []

    # Return only lines containing known modem vendor names
    return [
        line.strip()
        for line in stdout.splitlines()
        if any(vendor in line.lower() for vendor in MODEM_KEYWORDS)
    ]


def get_wifi_interfaces():
    """
    Detect available Wi-Fi interfaces using 'iwinfo'.
    Returns a unique list of interface names.
    """
    stdout, _, rc = run_local_command("iw phy | grep "wiphy index" | wc -l", allow_fail=True)   #need to report radio count

    # If Wi-Fi not available or command failed
    if rc != 0 or not stdout:
        return []

    # Extract first column (interface name) and remove duplicates
    return list({
        line.split()[0]
        for line in stdout.splitlines()
        if line.split()
    })


def main():

    # ---------------- CLI Parsing ----------------
    parser = argparse.ArgumentParser()
    parser.add_argument("config", help="CONFIGURATION='{\"expected_modems\":0,\"expected_wifi\":1}'")
    args = parser.parse_args()

    expected = parse_configuration(args.config)

    exp_modems = expected.get("expected_modems")
    exp_wifi = expected.get("expected_wifi")

    # Validate required input fields
    if exp_modems is None or exp_wifi is None:
        log("Missing expected_modems or expected_wifi in CONFIGURATION", level="FAIL")
        sys.exit(EXIT_FAILED)

    log("[STEP 1] Starting Modem & Wi-Fi Verification Test")

    # ---------------- Detection Phase ----------------
    modems = get_installed_modems()
    wifi = get_wifi_interfaces()

    log("Detected %s modem(s)", len(modems))
    log("Detected %s Wi-Fi interface(s)", len(wifi))

    # ---------------- Validation Phase ----------------
    test_passed = True

    # Check modem count
    if len(modems) == exp_modems:
        log("Modem count matches expected '%s'", exp_modems, level="PASS")
    else:
        log("Modem count expected '%s' but found '%s'", exp_modems, len(modems), level="FAIL")
        test_passed = False

    # Check Wi-Fi interface count
    if len(wifi) == exp_wifi:
        log("Wi-Fi count matches expected '%s'", exp_wifi, level="PASS")
    else:
        log("Wi-Fi count expected '%s' but found '%s'", exp_wifi, len(wifi), level="FAIL")
        test_passed = False

    # ---------------- Final Result ----------------
    if test_passed:
        log("Hardware verification successful", level="PASS")
        log("Test Case PASSED", level="PASS")
        sys.exit(EXIT_SUCCESS)
    else:
        log("Hardware verification failed", level="FAIL")
        log("Test Case FAILED", level="FAIL")
        sys.exit(EXIT_FAILED)


if __name__ == "__main__":
    main()

#python3 BB-SU-006.py CONFIGURATION='{ "expected_modems": 2, "expected_wifi": 1 }'
