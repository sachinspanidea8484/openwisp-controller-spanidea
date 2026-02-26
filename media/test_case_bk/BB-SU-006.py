# START_DESCRIPTION
# 1. Detect connected hardware components (modems, Wi-Fi radios).
# 2. Count installed USB cellular modems.
# 3. Detect Wi-Fi radio count using mandatory command.
# 4. Compare detected hardware count with expected inventory.
# 5. If hardware inventory matches expected values, mark test as PASSED.
# END_DESCRIPTION

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

# Known cellular modem vendor keywords
MODEM_KEYWORDS = ["telit", "quectel", "fibocom", "sierra", "huawei", "simcom"]


# -----------------------------------------------------------
# Detect Installed USB Cellular Modems
# -----------------------------------------------------------
def get_installed_modems():
    """
    Detect connected USB cellular modems using 'lsusb'.
    Returns list of modem description lines.
    """
    stdout, _, rc = run_local_command("lsusb", allow_fail=True)

    if rc != 0 or not stdout:
        return []

    return [
        line.strip()
        for line in stdout.splitlines()
        if any(vendor in line.lower() for vendor in MODEM_KEYWORDS)
    ]


# -----------------------------------------------------------
# Detect Wi-Fi Radios (MANDATORY COMMAND USED)
# -----------------------------------------------------------
def get_wifi_radio_count():
    """
    Detect number of Wi-Fi radios using mandatory command:
    iw phy | grep "wiphy index" | wc -l
    Returns integer radio count.
    """
    stdout, _, rc = run_local_command(
        'iw phy | grep "wiphy index" | wc -l',
        allow_fail=True
    )

    if rc != 0 or not stdout:
        return 0

    try:
        return int(stdout.strip())
    except ValueError:
        return 0


# -----------------------------------------------------------
# Main Test Execution
# -----------------------------------------------------------
def main():

    # ---------------- CLI Parsing ----------------
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "config",
        help='CONFIGURATION=\'{"expected_modems":0,"expected_wifi":1}\''
    )
    args = parser.parse_args()

    expected = parse_configuration(args.config)

    exp_modems = expected.get("expected_modems")
    exp_wifi = expected.get("expected_wifi")

    if exp_modems is None or exp_wifi is None:
        log("Missing expected_modems or expected_wifi in CONFIGURATION", level="FAIL")
        sys.exit(EXIT_FAILED)

    log("[STEP 1] Starting Modem & Wi-Fi Verification Test")

    # ---------------- Detection Phase ----------------
    modems = get_installed_modems()
    wifi_count = get_wifi_radio_count()

    log("Detected %s modem(s)", len(modems))
    log("Detected %s Wi-Fi radio(s)", wifi_count)

    # ---------------- Validation Phase ----------------
    test_passed = True

    # Validate modem count
    if len(modems) == exp_modems:
        log("Modem count matches expected '%s'", exp_modems, level="PASS")
    else:
        log(
            "Modem count expected '%s' but found '%s'",
            exp_modems,
            len(modems),
            level="FAIL"
        )
        test_passed = False

    # Validate Wi-Fi radio count
    if wifi_count == exp_wifi:
        log("Wi-Fi radio count matches expected '%s'", exp_wifi, level="PASS")
    else:
        log(
            "Wi-Fi radio count expected '%s' but found '%s'",
            exp_wifi,
            wifi_count,
            level="FAIL"
        )
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
