# START_DESCRIPTION 
#1. Initialize logging 
#2. Check the DUT connection and SIM status
#3. Check 5G Network Registration status.
#4. Check PCI/Cell Unlock status.
#5. Turn off PCI/cell lock.
#6. Verify that the DUT PCI Lock is Disable.
# END_DESCRIPTION


#!/usr/bin/env python3
"""
5G PCI UNLOCK  TEST (BB-INT-5G-005)
Dynamic target band input via command-line parameter
python3 BB_INT_5G_005.py CONFIGURATION='{"cellular_interface": "Modem1", "error_threshold_percent":"10"}'
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

def parse_c5greg(output):
    match = re.search(r"\+C5GREG:\s*\d+,(\d+)", output)
    return int(match.group(1)) if match else None


def parse_nrds(output):
    match = re.search(r"#NRDS:\s*(.+)", output)
    if not match:
        return None

    fields = match.group(1).split(",")

    try:
        band, bw = fields[0].split("/")
        return {
            "band": int(band),
            "bw": int(bw),
            "arfcn": int(fields[2]),
            "pci": int(fields[3]),
            "rsrp": int(fields[4]),
            "rsrq": int(fields[5]),
            "ssb_rsrp": int(fields[21]),
            "scs": int(fields[22]),
        }
    except (IndexError, ValueError):
        return None

def get_pci_lock_status(output):
    
    # AT#5GBCCHLOCK? : 0 -> PCI lock (SCS + ARFCN + PCI + BAND)
    #                  1 -> Frequency lock (SCS + ARFCN list)
    #                  2 -> Disabled
    
    match = re.search(r"#5GBCCHLOCK:\s*(.+)", output)
    if not match:
        return {
            "status": "UNKNOWN",
            "lock_type": None
        }

    fields = match.group(1).split(",")
    lock_type = fields[0].strip()

    if lock_type == "2":
        return {
            "status": "DISABLED",
            "lock_type": 2
        }

    if lock_type == "0" and len(fields) >= 5:
        return {
            "status": "ENABLED",
            "lock_type": 0,
            "scs": int(fields[1]),
            "arfcn": int(fields[2]),
            "pci": int(fields[3]),
            "band": int(fields[4])
        }

    if lock_type == "1" and len(fields) >= 3:
        locks = []
        i = 1
        while i + 1 < len(fields):
            locks.append({
                "scs": int(fields[i]),
                "arfcn": int(fields[i + 1])
            })
            i += 2

        return {
            "status": "ENABLED",
            "lock_type": 1,
            "frequencies": locks
        }

    return {
        "status": "UNKNOWN",
        "lock_type": None
    }

# === MAIN LOGIC ===
if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='5G PCI UNLOCK TEST (BB-INT-4G-005)')
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

     
    log("Starting 5G PCI UNLOCK Test BB-INT-4G-005...")
    
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



        # Step 3: Check PCI Lock Status 
        log("=== Step 3: Checking PCI Lock Status ===")

        lock_output, _ = at_cmd("AT#5GBCCHLOCK?")
        pci_lock_status = get_pci_lock_status(lock_output)

        log(f"PCI Lock is currently: {pci_lock_status}")

        # -------- Case 1: Already Disabled --------------------------

        if pci_lock_status["status"] != "ENABLED":

            log("PCI Lock is already DISABLED.")

            log("=== Step 4: Validating Interface Error Counters ===")

            if not validate_ifconfig_errors(DATA_INTERFACE, THRESHOLD):
                log("TEST FAILED: Interface error threshold exceeded.", level="ERROR")
                sys.exit(EXIT_FAILED)

            log("Interface error validation passed.")
            log("=== TEST PASSED — PCI already unlocked ===")
            sys.exit(EXIT_SUCCESS)


        # -------- Case 2: Unlock Required ----------------------------
        log("PCI Lock is ENABLED. Proceeding with UNLOCK...")

        at_cmd("AT#5GBCCHLOCK=2")
        time.sleep(5)


        # Step 4: Verify PCI Unlock 
        log("=== Step 4: Verifying PCI Unlock ===")

        lock_output, _ = at_cmd("AT#5GBCCHLOCK?")
        pci_lock_status = get_pci_lock_status(lock_output)

        log(f"PCI Lock is currently: {pci_lock_status}")

        if pci_lock_status["status"] == "ENABLED":
            log("PCI Lock is still ENABLED after unlock attempt.", level="ERROR")
            log("TEST FAILED — PCI unlock unsuccessful.")
            sys.exit(EXIT_FAILED)

        log("PCI Lock successfully DISABLED.")


        # Step 5: Validate Interface Errors 
        log("=== Step 5: Validating Interface Error Counters ===")

        if not validate_ifconfig_errors(DATA_INTERFACE, THRESHOLD):
            log("TEST FAILED: Interface error threshold exceeded.", level="ERROR")
            sys.exit(EXIT_FAILED)

        log("Interface error validation passed.")
        log("=== TEST PASSED — PCI Unlock successful ===")
        sys.exit(EXIT_SUCCESS)



    except Exception as e:
        log("TEST FAILED - Unhandled exception: %s", e, level="ERROR")
        sys.exit(EXIT_FAILED)