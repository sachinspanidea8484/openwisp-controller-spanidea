# START_DESCRIPTION 
#1. Verify band to which BB is currently attached
#2. Unlock the BB and let it select any available band, ARFCN, PCI 
#3. Verify that the band lock is turned off, the BB detaches from the first band and re-attached to an available band, ARFCN, PCI
# END_DESCRIPTION

#!/usr/bin/env python3
"""
5G BAND UNLOCK TEST (BB-INT-5G-007)
Dynamic target band input via command-line parameter
python3 BB_INT_5G_007.py CONFIGURATION='{"cellular_interface": "Modem1", "error_threshold_percent":"10"}'
"""


import re
import sys
import time
import argparse

from common_helper import (
    log,
    run_local_command,
    parse_config,
    get_modem_status,
    ensure_modem_connected,
    validate_ifconfig_errors,
    EXIT_SUCCESS,
    EXIT_FAILED
)

#CONSTANTS
MAX_RETRIES = 3
EXIT_SUCCESS = 0
EXIT_FAILED = 1
WAITING_TIME = 60
DEFAULT_BND = ["0", "22", "A7E2BB0F38DF", "42", "1A0290828D7", "7042", "81A03B0A38D7", "7C42"]


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

# ================= PARSERS =================
def parse_cpin(output):
    if not output:
        return "UNKNOWN"
    if "+CME ERROR: 10" in output:
        return "NOT_INSERTED"
    if "SIM PIN" in output:
        return "PIN_REQUIRED"
    if "SIM PUK" in output:
        return "PUK_REQUIRED"
    if "READY" in output:
        return "READY"
    return "UNKNOWN"


def parse_c5greg(output):
    m = re.search(r"\+C5GREG:\s*\d+,(\d+)", output or "")
    return int(m.group(1)) if m else None


def parse_bnd_status(output):
    m = re.search(r"#BND:\s*(.*)", output or "")
    if not m:
        return None

    fields = [x.strip() for x in m.group(1).split(",")]

    if fields == DEFAULT_BND:
        return {"status": "UNLOCKED"}

    return {
        "status": "LOCKED",
        "raw": fields
    }



def parse_rfsts_mode_and_band(output):
    m = re.search(r"#RFSTS:\s*(.*)", output or "")
    if not m:
        return {"mode": "UNKNOWN", "band": None}

    f = [x.strip().strip('"') for x in m.group(1).split(",")]

    # NR-SA
    if len(f) >= 7 and f[6].isdigit():
        return {"mode": "NR-SA", "band": f"n{f[6]}"}

    # NR-NSA
    for i in range(len(f)):
        if f[i].isdigit() and 1 <= int(f[i]) <= 258:
            return {"mode": "NR-NSA", "band": f"n{f[i]}"}

    # LTE fallback
    if f and f[-1].isdigit():
        return {"mode": "LTE", "band": f"B{f[-1]}"}

    return {"mode": "UNKNOWN", "band": None}


def band_to_bitmask(band):
    low, high = 0, 0
    if band <= 64:
        low = 1 << (band - 1)
    else:
        high = 1 << (band - 65)
    return f"{low:X}", f"{high:X}"



if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='5G BAND UNLOCK TEST (BB-INT-5G-007)')
    parser.add_argument('config', help='Configuration string')
    args = parser.parse_args()

    config = parse_config(args.config)

    CELLULAR_IFACE = config.get('cellular_interface', 'Modem1')
    THRESHOLD = float(config.get('error_threshold_percent', 10))

    BB_AT_PORT = "/dev/ttyUSB3" if CELLULAR_IFACE == "Modem1" else "/dev/ttyUSB7"

    log(f"Starting 5G BAND UNLOCK test (BB-INT-5G-007)...")

    try:
        # STEP 1: Modem Info
        info = get_modem_status(CELLULAR_IFACE)
        if not info:
            log("TEST FAILED - Unable to get modem status", level="ERROR")
            sys.exit(EXIT_FAILED)

        QMI_DEVICE = info["qmi_device"]
        DATA_INTERFACE = info["data_interface"]

        log("Modem Info - QMI: %s | Interface: %s", QMI_DEVICE, DATA_INTERFACE)

        # STEP 2: Ensure Connection
        log("=== STEP 2: Checking Modem Connection ===")
        if not ensure_modem_connected(CELLULAR_IFACE, QMI_DEVICE):
            log("TEST FAILED - Modem not connected", level="ERROR")
            sys.exit(EXIT_FAILED)

        # STEP 3: SIM Check
        log("=== STEP 3: Checking SIM Status ===")
        sim_out, _ = at_cmd("AT+CPIN?")
        sim_status = parse_cpin(sim_out)

        if sim_status != "READY":
            log(f"TEST FAILED - SIM state: {sim_status}", level="ERROR")
            sys.exit(EXIT_FAILED)

        # STEP 4: Current RAT & Band
        log("=== STEP 4: Current RAT & Band ===")
        rf_out, _ = at_cmd("AT#RFSTS")
        rf = parse_rfsts_mode_and_band(rf_out)
        log(f"Current RAT={rf['mode']} Band={rf['band']}")

        # STEP 5: Check Current BND Configuration
        log("=== STEP 5: Checking Band Configuration (Before Unlock) ===")
        bnd_before_out, _ = at_cmd("AT#BND?")
        bnd_before = parse_bnd_status(bnd_before_out)

        if not bnd_before:
            log("TEST FAILED - Unable to parse BND status", level="ERROR")
            sys.exit(EXIT_FAILED)

        if bnd_before["status"] == "UNLOCKED":
            log("Band configuration already UNLOCKED (default)")
            
            log("=== Step 2: Validating Interface Error Counters ===")

            if not validate_ifconfig_errors(DATA_INTERFACE, THRESHOLD):
                log("TEST FAILED: Interface error threshold exceeded.", level="ERROR")
                sys.exit(EXIT_FAILED)

            log("Interface error validation passed.")
            log("=== TEST PASSED — Band Unlock already enabled ===")
            sys.exit(EXIT_SUCCESS)
            
        log("Band lock is ENABLED. Current config: %s", bnd_before)    

        # STEP 6: Send Unlock Command
        log("=== STEP 6: Sending Band Unlock Command ===")
        unlock_out, _ = at_cmd("AT#BND=0,22,A7E2BB0F38DF,42,1A0290828D7,7042,81A03B0A38D7,7C42") 
        
        if "OK" not in unlock_out:
            log("TEST FAILED - Unlock command failed", level="ERROR")
            sys.exit(EXIT_FAILED)

        # STEP 7: Verify BND After Unlock
        log("=== STEP 7: Verifying Band Configuration (After Unlock) ===")
        bnd_after_out, _ = at_cmd("AT#BND?")
        bnd_after = parse_bnd_status(bnd_after_out)

        if not bnd_after:
            log("TEST FAILED - Unable to parse BND after unlock", level="ERROR")
            sys.exit(EXIT_FAILED)

        log(f"BND Status After Unlock: {bnd_after}")

        if bnd_after["status"] != "UNLOCKED":
            log("TEST FAILED - BND still LOCKED after unlock command", level="ERROR")
            sys.exit(EXIT_FAILED)

        if bnd_before == bnd_after:
            log("NOTE - BND configuration unchanged (already unlocked)")

        
        # STEP 8: Verify RAT & Band After Unlock
        log("=== STEP 8: Verifying RAT & Band After Unlock ===")
        rf_verify_out, _ = at_cmd("AT#RFSTS")
        rf_new = parse_rfsts_mode_and_band(rf_verify_out)
        log(f"RAT={rf_new['mode']} Band={rf_new['band']}")

        # Check if band changed
        if rf_new['band'] != rf['band']:
            log("Band unlock successful — band changed after unlock")
        else:
            log("TEST FAILED — band did not change after unlock", level="ERROR")
            sys.exit(EXIT_FAILED)


        # STEP 9: Validate Interface Errors
        log("=== STEP 9: Validating Interface Error Counters ===")
        if not validate_ifconfig_errors(DATA_INTERFACE, THRESHOLD):
            log("TEST FAILED: Interface error threshold exceeded.", level="ERROR")
            sys.exit(EXIT_FAILED)

        log("Interface error validation passed.")

        # FINAL RESULT
        log("=== TEST PASSED — 5G Band Unlock successful ===")
        sys.exit(EXIT_SUCCESS)

    except Exception as e:
        log("TEST FAILED - Unhandled exception: %s", e, level="ERROR")
        sys.exit(EXIT_FAILED)
