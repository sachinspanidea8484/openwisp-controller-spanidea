# START_DESCRIPTION 
#1. Initialize logging
#2. Attach the DUT to the 5G network and verify.
#3. Check the DUT connection, signal information.
#4. Verify connectivity by ping from DUT to PC (remote=8.8.8.8)
# END_DESCRIPTION



#!/usr/bin/env python3
"""
5G WAN INTERFACE TEST (BB-INT-5G-001)
Dynamic target band input via command-line parameter
python3 BB-INT-5G-001.py CONFIGURATION='{"cellular_interface": "wwan1", "remote_ping_ip": "8.8.8.8", "test_duration" : "60", "error_threshold_percent":"10"}'
"""

import os
import re
import sys
import time
import json
import argparse
from datetime import datetime
from common_helper import (log, run_local_command, parse_config, validate_ifconfig_errors, EXIT_SUCCESS,EXIT_FAILED)



#CONSTANTS
MAX_RETRIES = 3
EXIT_SUCCESS = 0
EXIT_FAILED = 1


def get_modem_status(interface):
    log(f"Getting modem full status for {interface}...")

    # STEP 1: Get all modem sections from UCI
    stdout, _, rc = run_local_command("uci show network | grep '.device='", allow_fail=True)

    if rc != 0 or not stdout.strip():
        log("No modem entries found in UCI", level="FAIL")
        return None

    modem_sections = set()
    for line in stdout.splitlines():
        try:
            section = line.split('.')[1]
            modem_sections.add(section)
        except Exception:
            continue

    modem_name = None
    qmi_device = None

    # STEP 2: Map interface -> modem
    for modem in modem_sections:
        stdout, _, rc = run_local_command(f"ifstatus {modem}", allow_fail=True)
        if rc != 0 or not stdout:
            continue

        try:
            status_json = json.loads(stdout)
            if status_json.get("l3_device") == interface:
                dev_out, _, rc_dev = run_local_command(f"uci -q get network.{modem}.device", allow_fail=True)
                if rc_dev == 0 and dev_out:
                    qmi_device = dev_out.strip()
                    modem_name = modem
                    break
        except Exception:
            continue

    if not qmi_device:
        log(f"No modem mapped to interface {interface}", level="FAIL")
        return None

    # STEP 3: Get USB Device Root
    qmi_base = os.path.basename(qmi_device)
    stdout, _, rc = run_local_command(f"readlink -f /sys/class/usbmisc/{qmi_base}/device/..", allow_fail=True)

    if rc != 0 or not stdout.strip():
        log("Failed to determine USB parent path", level="FAIL")
        return None

    usb_device_root = stdout.strip()

    # STEP 4: Detect AT Port (Fixed duplicate probing)
    # Using -maxdepth 2 avoids finding nested paths like .../ttyUSB0/tty/ttyUSB0
    stdout, _, rc = run_local_command(f"find {usb_device_root} -maxdepth 2 -name 'ttyUSB*'", allow_fail=True)
    
    at_port = None
    if rc == 0 and stdout:
        # Using a set comprehension to ensure each port is unique (e.g., /dev/ttyUSB0)
        unique_ports = {f"/dev/{os.path.basename(p.strip())}" for p in stdout.splitlines() if 'ttyUSB' in p}
        potential_ports = sorted(list(unique_ports))
        
        for tty_dev in potential_ports:
            # Probing with a 1s timeout
            probe_cmd = f"echo 'AT' | socat -T 1 - '{tty_dev},raw,echo=0,crnl'"
            resp, _, _ = run_local_command(probe_cmd, allow_fail=True)

            if resp and "OK" in resp:
                at_port = tty_dev
                break

    if not at_port:
        log("No functional AT port detected", level="WARN")

    # STEP 5: Detect Network Type via QMI (Fixed False 5G detection)
    stdout, _, rc = run_local_command(f"qmicli -d {qmi_device} --nas-get-signal-info", allow_fail=True)
    
    network_type = "No Signal"
    if rc == 0 and stdout:
        # We look for the 5G section and ensure RSRP is actually a number, not 'n/a'
        # re.DOTALL allows the '.' to match newlines
        has_5g = re.search(r"5G:.*?RSRP:\s+'-\d+", stdout, re.DOTALL | re.IGNORECASE)
        has_lte = re.search(r"LTE:.*?RSRP:\s+'-\d+", stdout, re.DOTALL | re.IGNORECASE)

        if has_5g:
            network_type = "5G"
        elif has_lte:
            network_type = "4G"

    return {
        "interface": interface,
        "modem_name": modem_name,
        "qmi_device": qmi_device,
        "usb_device_root": usb_device_root,
        "at_port": at_port,
        "network_type": network_type
    }



def ensure_modem_connected(modem_iface,qmi_device):
    log("Checking modem connection status...")

    for attempt in range(1, MAX_RETRIES + 1):

        status_out, stderr, rc = run_local_command(f"uqmi -d {qmi_device} --get-data-status",allow_fail=True)

        status_out = status_out.strip().strip('"')

        if status_out.lower() == "connected":
            log("Modem is connected.")
            return True

        log("Attempt %d/%d: Modem disconnected (%s), retrying...",
            attempt, MAX_RETRIES, status_out)

        run_local_command(f"ifup {modem_iface}", allow_fail=True)
        time.sleep(30)

    log("Modem failed to connect after max retries.", level="ERROR")
    return False  


    
def ping_remote(iface, remote_ip):
    log("Pinging %s via %s...", remote_ip, iface)

    stdout, stderr, rc = run_local_command(f"ping -I {iface} -c 4 {remote_ip}",allow_fail=True)

    # Print full ping output
    if stdout:
        log("Ping Output:\n%s", stdout)

    if rc != 0 or "100% packet loss" in stdout or "0 received" in stdout:
        log("Ping failed.", level="ERROR")
        return False

    log("Ping successful.")
    return True

   
# === MAIN LOGIC ===
if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='5G WAN INTERFACE (BB-INT-5G-001)')
    parser.add_argument('config', help='Configuration string')
    args = parser.parse_args()

    config = parse_config(args.config)

    CELLULAR_IFACE = config.get('cellular_interface', 'wwan1')
    REMOTE_PING_IP = config.get('remote_ping_ip', '8.8.8.8')
    TEST_DURATION = int(config.get('test_duration', 60))
    THRESHOLD = float(config.get('error_threshold_percent', 10))

    log("Starting 5G WAN Interface Test BB-INT-5G-001...")

    try:
        info = get_modem_status(CELLULAR_IFACE)

        if not info:
            log("TEST FAILED - Failed to get modem status", level="ERROR")
            sys.exit(EXIT_FAILED)

        QMI_DEVICE = info["qmi_device"]
        MODEM_INTERFACE = info["modem_name"]
        NETWORK_TYPE = info["network_type"]
        log("Modem Info - QMI Device: %s | Modem Interface: %s | Network Type: %s",QMI_DEVICE, MODEM_INTERFACE, NETWORK_TYPE)

        if not ensure_modem_connected(MODEM_INTERFACE, QMI_DEVICE):
            log("TEST FAILED - Modem failed to connect", level="ERROR")
            sys.exit(EXIT_FAILED)

        if NETWORK_TYPE != "5G":
            log("TEST FAILED - %s is not a 5G WAN interface but has %s",
            CELLULAR_IFACE, NETWORK_TYPE, level="ERROR")
            sys.exit(EXIT_FAILED)

      
        if not ping_remote(CELLULAR_IFACE, REMOTE_PING_IP):
            log("TEST FAILED - Initial connectivity check failed", level="ERROR")
            sys.exit(EXIT_FAILED)

        
        log("Initial connectivity check PASSED: %s via %s .",NETWORK_TYPE, CELLULAR_IFACE)

        # Stability Test
        log("Starting %d seconds stability test...", TEST_DURATION)

        start = time.time()

        while time.time() - start < TEST_DURATION:
            if not ping_remote(CELLULAR_IFACE, REMOTE_PING_IP):
                log("TEST FAILED - Ping failed during stability test", level="ERROR")
                sys.exit(EXIT_FAILED)
            time.sleep(30)

        log("TEST PASSED - Stability test completed successfully for %d seconds",
            TEST_DURATION)
        
        # Validate interface errors
        if not validate_ifconfig_errors(CELLULAR_IFACE, THRESHOLD):
            sys.exit(EXIT_FAILED)

        log("TEST PASSED - Stability and IFCONFIG validation successful")
        sys.exit(EXIT_SUCCESS)

    except Exception as e:
        log("TEST FAILED - Unhandled exception: %s", e, level="ERROR")
        sys.exit(EXIT_FAILED)
