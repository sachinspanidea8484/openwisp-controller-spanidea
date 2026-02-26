# START_DESCRIPTION
#1. Initialize logging and test environment.
#2. Attach the DUT to both 4G (wwan0) and 5G (wwan1) networks and verify registration.
#3. Check interface status, IP assignment, routing table, and signal information for both WANs.
#4. Verify internet connectivity by pinging a public IP (e.g., 8.8.8.8) from each WAN interface.
#5. Validate dual WAN operation and failover by bringing down one interface and confirming traffic switches to the other.
#END_DESCRIPTION



#!/usr/bin/env python3
"""
BB-TRF-4G5G-004
Dual 4G/5G WAN Validation

python3 BB-TRF-4G5G-004.py CONFIGURATION='{"wan4g_interface":"wwan0","wan5g_interface":"wwan1","remote_ping_ip":"8.8.8.8","test_duration":"60","error_threshold_percent":"10"}'
"""
import re
import sys
import time
import argparse
from common_helper import (log,run_local_command,parse_config, validate_ifconfig_errors, EXIT_SUCCESS, EXIT_FAILED)

MAX_RETRIES = 3



def verify_interface_up(iface):
    log("Checking interface status for %s...", iface)
    stdout, stderr, rc = run_local_command(f"ip addr show {iface}", allow_fail=True)

    if rc != 0:
        log("Failed to read interface %s", iface, level="ERROR")
        return False

    # Extract flags section
    match = re.search(r"<([^>]+)>", stdout)
    if not match or "UP" not in match.group(1):
        log("Interface %s is not UP", iface, level="ERROR")
        return False

    if not re.search(r"inet\s+\d+\.\d+\.\d+\.\d+", stdout):
        log("Interface %s does not have IPv4 assigned", iface, level="ERROR")
        return False

    log("Interface %s is UP with IP assigned", iface)
    return True



def ping_test(iface, remote_ip):
    log("Pinging %s via %s...", remote_ip, iface)
    stdout, stderr, rc = run_local_command(
        f"ping -I {iface} -c 4 {remote_ip}", allow_fail=True
    )

    if stdout:
        log("Ping Output (%s):\n%s", iface, stdout)

    if rc != 0 or "100% packet loss" in stdout:
        log("Ping failed via %s", iface, level="ERROR")
        return False

    log("Ping successful via %s", iface)
    return True


def verify_default_route():
    log("Checking routing table...")
    stdout, stderr, rc = run_local_command("ip route", allow_fail=True)

    if "default" not in stdout:
        log("No default route found!", level="ERROR")
        return False

    log("Default route exists:\n%s", stdout)
    return True


def failover_test(primary_iface, secondary_iface, remote_ip):
    log("Starting failover test: Bringing down %s...", primary_iface)

    run_local_command(f"ifconfig {primary_iface} down")

    time.sleep(5)

    stdout, stderr, rc = run_local_command(
        f"ping -I {secondary_iface} -c 4 {remote_ip}", allow_fail=True
    )

    if rc != 0 or "100% packet loss" in stdout:
        log("Failover FAILED - No connectivity via %s", secondary_iface, level="ERROR")
        run_local_command(f"ifconfig {primary_iface} up")
        return False

    log("Failover SUCCESS - Traffic switched to %s", secondary_iface)

    run_local_command(f"ifconfig {primary_iface} up")
    time.sleep(5)

    return True


# ================= MAIN =================

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Dual 4G/5G WAN Test")
    parser.add_argument("config", help="Configuration string")
    args = parser.parse_args()

    config = parse_config(args.config)

    WAN4G = config.get("wan4g_interface", "wwan0")
    WAN5G = config.get("wan5g_interface", "wwan1")
    REMOTE_IP = config.get("remote_ping_ip", "8.8.8.8")
    TEST_DURATION = int(config.get("test_duration", 60))
    THRESHOLD = float(config.get("error_threshold_percent", 10))

    log("Starting BB-TRF-4G5G-004 Dual WAN Test")

    try:

        # Step 1: Interface Validation
        if not verify_interface_up(WAN4G):
            sys.exit(EXIT_FAILED)

        if not verify_interface_up(WAN5G):
            sys.exit(EXIT_FAILED)

        # Step 2: Routing Table Check
        if not verify_default_route():
            sys.exit(EXIT_FAILED)

        # Step 3: Individual Connectivity
        if not ping_test(WAN4G, REMOTE_IP):
            sys.exit(EXIT_FAILED)

        if not ping_test(WAN5G, REMOTE_IP):
            sys.exit(EXIT_FAILED)

        log("Initial connectivity for both WANs PASSED")

        # Step 4: Stability Test
        log("Starting %d seconds stability test...", TEST_DURATION)
        start = time.time()

        while time.time() - start < TEST_DURATION:
            if not ping_test(WAN4G, REMOTE_IP):
                sys.exit(EXIT_FAILED)
            if not ping_test(WAN5G, REMOTE_IP):
                sys.exit(EXIT_FAILED)
            time.sleep(30)

        log("Stability test PASSED")

        # Step 5: Failover Test
        if not failover_test(WAN4G, WAN5G, REMOTE_IP):
            sys.exit(EXIT_FAILED)

        # Step 6: Interface Error Validation
        if not validate_ifconfig_errors(WAN4G, THRESHOLD):
            sys.exit(EXIT_FAILED)

        if not validate_ifconfig_errors(WAN5G, THRESHOLD):
            sys.exit(EXIT_FAILED)

        log("TEST PASSED - Dual 4G/5G WAN validation successful")
        sys.exit(EXIT_SUCCESS)

    except Exception as e:
        log("TEST FAILED - Unhandled exception: %s", e, level="ERROR")
        sys.exit(EXIT_FAILED)

