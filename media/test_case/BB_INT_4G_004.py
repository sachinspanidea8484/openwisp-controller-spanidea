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
python3 BB_INT_4G_004.py CONFIGURATION='{"cellular_interface": "Modem1", "error_threshold_percent":"10"}'
"""


import re
import sys
import time
import json
import argparse
from datetime import datetime
from common_helper import (log, run_local_command, parse_config, get_modem_status, ensure_modem_connected, validate_ifconfig_errors, EXIT_SUCCESS,EXIT_FAILED)



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

    CELLULAR_IFACE = config.get('cellular_interface', 'Modem1')
    THRESHOLD = float(config.get('error_threshold_percent', 10))
                               
    
    if CELLULAR_IFACE == "Modem1":
        BB_AT_PORT = "/dev/ttyUSB3"
    elif CELLULAR_IFACE == "Modem2":
        BB_AT_PORT = "/dev/ttyUSB7"
    else:
        BB_AT_PORT = None

     
    log("Starting 4G PCI UNLOCK Test BB-INT-4G-004...")
    
    try:
        info = get_modem_status(CELLULAR_IFACE)

        if not info:
            log("TEST FAILED - Failed to get modem status", level="ERROR")
            sys.exit(EXIT_FAILED)

        QMI_DEVICE = info["qmi_device"]
        DATA_INTERFACE = info["data_interface"]
        NETWORK_TYPE = info["network_type"]
        log("Modem Info - QMI Device: %s | Data Interface: %s | Network Type: %s",QMI_DEVICE, DATA_INTERFACE, NETWORK_TYPE)

            
        # Step 1: Ensure modem is connected
        log("=== Step 1: Checking Modem Connection Status ===")
        if not ensure_modem_connected(CELLULAR_IFACE, QMI_DEVICE):
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

        if not validate_ifconfig_errors(DATA_INTERFACE, THRESHOLD):
            log("TEST FAILED: Interface error threshold exceeded.", level="ERROR")
            sys.exit(EXIT_FAILED)

        log("Interface error validation passed.")

        # Final result
        log("=== TEST PASSED ===")
        sys.exit(EXIT_SUCCESS)



    except Exception as e:
        log("TEST FAILED - Unhandled exception: %s", e, level="ERROR")
        sys.exit(EXIT_FAILED)