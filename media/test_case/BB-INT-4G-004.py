# START_DESCRIPTION 
#1. Initialize logging 
#2. Check the DUT connection and SIM status
#3. Check Network Registration status.
#4. Check PCI/Cell Unlock status.
#5. Turn off PCI/cell lock.
#6. Verify that the DUT PCI Lock is Disable.
# END_DESCRIPTION


#!/usr/bin/env python3
"""
4G PCI UNLOCK  TEST (BB-INT-4G-004)
Dynamic target band input via command-line parameter
python3 BB-INT-4G-004.py CONFIGURATION='{"cellular_interface": "wwan0", "error_threshold_percent":"10"}'
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


# === AT COMMAND HELPER FUNCTIONS  ===
def at_cmd(cmd):
    full_cmd = f'echo -e "{cmd}\\r" | socat - {BB_AT_PORT},raw,echo=0,crnl'
    stdout, stderr, rc = run_local_command(full_cmd, allow_fail=True)

    if stdout:
            log("OUT: %s", stdout)

    if stderr:
            log("ERR: %s",stderr, level="ERROR")

    if rc != 0:
        log("AT command failed (RC=%d): %s", rc, cmd, level="ERROR")

    if stdout and "ERROR" in stdout:
        log("Modem responded with ERROR for command: %s", cmd, level="ERROR")

    return stdout, stderr


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


# === Parsers ===
def parse_lteds(output):
    match = re.search(r"#LTEDS:\s*(\d+)/\d+,[^,]*,[^,]*,[^,]*,[^,]*,(\d+)\((\d+)\)", output)
    if match:
        return {
            "earfcn": int(match.group(1)),
            "cellid": int(match.group(2)),
            "pci": int(match.group(3))
        }
    return None

def parse_bcchlock(output):
    match = re.search(r"#BCCHLOCK:\s*\d+,\d+,\d+,(\d+),([0-9A-Fa-f]+)", output)
    if match:
        earfcn = int(match.group(1))
        pci = int(match.group(2), 16)
        lock_enabled = not (earfcn == 0 and pci == 0)
        return {"earfcn": earfcn, "pci": pci, "lock_enabled": lock_enabled}
    return None

def parse_cereg(output):
    match = re.search(r"\+CEREG:\s*\d+,(\d+)", output)
    return int(match.group(1)) if match else None

def parse_cpin(output):
    if "+CME ERROR: 10" in output:
        return "NOT_INSERTED"
    elif "SIM PIN" in output:
        return "PIN_REQUIRED"
    elif "SIM PUK" in output:
        return "PUK_REQUIRED"
    elif "READY" in output:
        return "READY"
    return "UNKNOWN"

def parse_cgatt(output):
    if "+CGATT: 1" in output:
        return True
    elif "+CGATT: 0" in output:
        return False
    return None


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='4G PCI UNLOCK TEST (BB-INT-4G-004)')
    parser.add_argument('config', help='Configuration string')
    args = parser.parse_args()

    config = parse_config(args.config)

    CELLULAR_IFACE = config.get('cellular_interface', 'wwan0')
    THRESHOLD = float(config.get('error_threshold_percent', 10))
                               
    

     
    log("Starting 4G PCI UNLOCK Test BB-INT-4G-004...")
    
    try:
        info = get_modem_status(CELLULAR_IFACE)

        if not info:
            log("TEST FAILED - Failed to get modem status", level="ERROR")
            sys.exit(EXIT_FAILED)

        QMI_DEVICE = info["qmi_device"]
        MODEM_INTERFACE = info["modem_name"]
        BB_AT_PORT = info["at_port"]
        NETWORK_TYPE = info["network_type"]
        log("Modem Info - QMI Device: %s | Modem Interface: %s | Network Type: %s",QMI_DEVICE, MODEM_INTERFACE, NETWORK_TYPE)
        log("AT Port: %s" ,BB_AT_PORT)

            
        # Step 1: Ensure modem is connected
        log("=== Step 1: Checking Modem Connection Status ===")
        if not ensure_modem_connected(MODEM_INTERFACE, QMI_DEVICE):
            log("TEST FAILED: Modem failed to connect.", level="ERROR")
            sys.exit(EXIT_FAILED)
        log("Modem connection: OK")    

        # Step 2: Check SIM
        log("=== Step 2: Checking SIM Status ===")
        sim_out, _ = at_cmd("AT+CPIN?")
        sim_status = parse_cpin(sim_out)

        if sim_status == "NOT_INSERTED":
            log("TEST FAILED: SIM not inserted.", level="ERROR")
            sys.exit(EXIT_FAILED)
        elif sim_status == "PIN_REQUIRED":
            log("TEST FAILED: SIM requires PIN.", level="ERROR")
            sys.exit(EXIT_FAILED)
        elif sim_status == "PUK_REQUIRED":
            log("TEST FAILED: SIM requires PUK.", level="ERROR")
            sys.exit(EXIT_FAILED)
        elif sim_status == "READY":
            log("SIM status: READY")
        else:
            log("TEST FAILED: Unknown SIM state. Response: %s", sim_out, level="ERROR")
            sys.exit(EXIT_FAILED)


    
        # Step 3: Check if PCI lock is enabled
        log("=== Step 3: Checking Current PCI Lock State ===")
        bcchlock_out, _ = at_cmd("AT#BCCHLOCK?")
        bcch_status = parse_bcchlock(bcchlock_out)

        if not bcch_status:
            log("TEST FAILED: Unable to parse BCCHLOCK response.", level="ERROR")
            sys.exit(EXIT_FAILED)

        if not bcch_status["lock_enabled"]:
            log("TEST FAILED: PCI Lock is already DISABLED.", level="ERROR")
            sys.exit(EXIT_FAILED)

        log("PCI Lock currently ENABLED (EARFCN=%d, PCI=%d / 0x%X)",
            bcch_status["earfcn"],
            bcch_status["pci"],
            bcch_status["pci"])

        log("Sending command to DISABLE PCI Lock...")
        at_cmd("AT#BCCHLOCK=1024,0,65535,0,0")
        time.sleep(3)


        # Step 4: Confirm PCI lock is disabled
        log("=== Step 4: Verifying PCI Lock Disabled ===")

        bcchlock_output, _ = at_cmd("AT#BCCHLOCK?")
        bcch_status = parse_bcchlock(bcchlock_output)

        # Step 4A: Validate lock state
        if not bcch_status:
            log("TEST FAILED: Unable to parse BCCHLOCK response.", level="ERROR")
            sys.exit(EXIT_FAILED)

        if (bcch_status["lock_enabled"] or
            bcch_status["earfcn"] != 0 or
            bcch_status["pci"] != 0):

            log("TEST FAILED: PCI Lock disable verification failed.", level="ERROR")
            sys.exit(EXIT_FAILED)

        log("PCI Lock successfully DISABLED.")

        # Step 4B: Validate interface errors
        log("=== Step 5: Validating Interface Error Counters ===")

        if not validate_ifconfig_errors(CELLULAR_IFACE, THRESHOLD):
            log("TEST FAILED: Interface error threshold exceeded.", level="ERROR")
            sys.exit(EXIT_FAILED)

        log("Interface error validation passed.")

        # Final result
        log("=== TEST PASSED ===")
        sys.exit(EXIT_SUCCESS)



    except Exception as e:
        log("TEST FAILED - Unhandled exception: %s", e, level="ERROR")
        sys.exit(EXIT_FAILED)
