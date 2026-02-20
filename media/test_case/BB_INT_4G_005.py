# START_DESCRIPTION 
#1. Verify band to which BB is currently attached
#2. Perform band lock to set band to a different band
#3. Verify that the BB detaches from the first band and re-attached to the specific band.
# END_DESCRIPTION


#!/usr/bin/env python3
"""
4G BAND LOCK  TEST (BB-INT-4G-005)
Dynamic target band input via command-line parameter
python3 BB_INT_4G_005.py CONFIGURATION='{"cellular_interface": "Modem1", "error_threshold_percent":"10", "LOCK_BAND": "66"}'
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
DEFAULT_BND = ["0", "22", "A7E2BB0F38DF", "42", "1A0290828D7", "7042", "81A03B0A38D7", "7C42"]
WAITING_TIME = 120  # seconds


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
def parse_cops(output):
    match = re.search(r'\+COPS:.*?,.*?,\"([^\"]+)\",(\d+)', output)
    if match:
        operator = match.group(1)
        act_code = int(match.group(2))
        act_map = {
            0: "GSM (2G)",
            2: "UTRAN (3G)",
            7: "E-UTRAN (4G LTE)",
            12: "NG-RAN (5G SA)",
            13: "E-UTRA-NR (5G NSA)"
        }
        act_name = act_map.get(act_code, f"Unknown ({act_code})")
        return {"operator": operator, "act_code": act_code, "act_name": act_name}
    return None

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


def parse_cereg(output):
    match = re.search(r"\+CEREG:\s*\d+,(\d+)", output)
    return int(match.group(1)) if match else None


def parse_bnd(output):
    match = re.search(r"#BND:\s*(.*)", output)
    if match:
        return [x.strip() for x in match.group(1).split(",")]
    return None

def parse_lteds(output):
    match = re.search(r"#LTEDS:.*?,(\d+),", output)
    return int(match.group(1)) if match else None

def parse_rfsts(output):
    match = re.search(r"#RFSTS:.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,\"([^\"]+)\",(\d+),(\d+)", output)
    if match:
        operator = match.group(1)
        tech = match.group(2)
        band = match.group(3)
        return {"operator": operator, "tech": tech, "band": int(band)}
    return None


# === BAND HELPERS ===
def band_to_bitmask(band_num):
    if not (1 <= band_num <= 128):
        raise ValueError("Band must be between 1 and 128")
    low_mask, high_mask = 0, 0
    if band_num <= 64:
        low_mask = 1 << (band_num - 1)
    else:
        high_mask = 1 << (band_num - 65)
    return f"{low_mask:X}", f"{high_mask:X}"


def get_band_config():
    out, _ = at_cmd("AT#BND?")
    bands = parse_bnd(out)
    if bands:
        log(f"Current Band Config: {bands}")
    else:
        log("Failed to read band configuration.")
    return bands

def set_band_config(config):
    cmd = f"AT#BND={','.join(config)}"
    at_cmd(cmd)
    time.sleep(3)
    return get_band_config()

def verify_current_band():
    time.sleep(5)
    out1, _ = at_cmd("AT#LTEDS")
    band = parse_lteds(out1)
    if band:
        log(f"Detected LTE band (from LTEDS): {band}")
    time.sleep(10)
    out2, _ = at_cmd("AT#RFSTS")
    info = parse_rfsts(out2)
    if info:
        log(f"Connected Operator: {info['operator']} | LTE Band: {info['band']}")
    return band

def lock_band(band_num):
    log(f"Locking modem to LTE Band {band_num} ...")
    low_mask, high_mask = band_to_bitmask(band_num)
    new_cfg = ["0", "0", low_mask, high_mask, "1A0290828D7", "7042", "81A03B0A38D7", "7C42"]
    set_band_config(new_cfg)
    time.sleep(5)



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='4G BAND LOCK TEST (BB-INT-4G-005)')
    parser.add_argument('config', help='Configuration string')
    args = parser.parse_args()

    config = parse_config(args.config)

    CELLULAR_IFACE = config.get('cellular_interface', 'Modem1')
    TARGET_BAND = int(config.get('LOCK_BAND', 66))
    THRESHOLD = float(config.get('error_threshold_percent', 10))
    
    if CELLULAR_IFACE == "Modem1":
        BB_AT_PORT = "/dev/ttyUSB3"
    elif CELLULAR_IFACE == "Modem2":
        BB_AT_PORT = "/dev/ttyUSB7"
    else:
        BB_AT_PORT = None

     
    log(f"Starting 4G BAND LOCK Test BB-INT-4G-005 with target band {TARGET_BAND}...")
    
    try:
        info = get_modem_status(CELLULAR_IFACE)

        if not info:
            log("TEST FAILED - Failed to get modem status", level="ERROR")
            sys.exit(EXIT_FAILED)

        QMI_DEVICE = info["qmi_device"]
        DATA_INTERFACE = info["data_interface"]
        NETWORK_TYPE = info["network_type"]

        log("Modem Info - QMI Device: %s | Data Interface: %s | Network Type: %s",
            QMI_DEVICE, DATA_INTERFACE, NETWORK_TYPE)

         # === Pre-check 1: Modem Connection ===
        log("=== Pre-check 1: Checking Modem Connection Status ===")
        if not ensure_modem_connected(CELLULAR_IFACE, QMI_DEVICE):
            log("TEST FAILED - Modem failed to connect.", level="ERROR")
            sys.exit(EXIT_FAILED)

        log("Modem connection: OK")
        
        # === Pre-check 2: SIM Status ===
        log("=== Pre-check 2: Checking SIM Status ===")
        sim_out, _ = at_cmd("AT+CPIN?")
        sim_status = parse_cpin(sim_out)

        if sim_status != "READY":
            log(f"TEST FAILED - SIM state invalid: {sim_status}", level="ERROR")
            sys.exit(EXIT_FAILED)

        log("SIM status: READY")
       
        # === Pre-check 3: Network Registration ===
        log("=== Pre-check 3: Checking Network Registration ===")
        nw_status_out, _ = at_cmd("AT+CEREG?")
        reg_status = parse_cereg(nw_status_out)

        if reg_status not in [1, 5]:
            log(f"TEST FAILED - Not registered to 4G network (CEREG={reg_status})", level="ERROR")
            sys.exit(EXIT_FAILED)

        log(f"Registered to 4G network ({'Home' if reg_status == 1 else 'Roaming'})")


        # === STEP 1: Verify current attached band ===
        log("=== STEP 1: Verify current LTE band ===")
        band1 = verify_current_band()

        if band1 is None:
            log("TEST FAILED - Unable to determine current LTE band", level="ERROR")
            sys.exit(EXIT_FAILED)

        log(f"Currently attached to LTE Band {band1}")

        if band1 == TARGET_BAND:
            log(f"TEST FAILED - Already on target Band {TARGET_BAND}. "
                "Cannot validate band switch.", level="ERROR")
            sys.exit(EXIT_FAILED)

        # === STEP 2: Perform band lock ===
        log(f"=== STEP 2: Locking to LTE Band {TARGET_BAND} ===")
        lock_band(TARGET_BAND)

        log(f"Waiting {WAITING_TIME}s for network reacquisition...")
        time.sleep(WAITING_TIME)

        # === STEP 3: Verify detach + reattach (with one retry) ===
        log("=== STEP 3: Verify band switch ===")

        max_attempts = 2   # 1 initial + 1 retry
        attempt = 1
        band2 = None
        band_switch_success = False

        while attempt <= max_attempts:

            log("Verification attempt %d/%d...", attempt, max_attempts)

            band2 = verify_current_band()

            if band2 is not None:
                log("Detected Band: %s", band2)

                if band2 != band1 and band2 == TARGET_BAND:
                    log("BB successfully detached from Band %s and reattached to Band %s",
                        band1, TARGET_BAND)
                    band_switch_success = True
                    break

            if attempt < max_attempts:
                log("Band verification failed. Waiting 10s before retry...")
                time.sleep(10)

            attempt += 1


        # === After Retry Loop ===
        if not band_switch_success:
            log("TEST FAILED - Expected Band %s, but final detected Band is %s",
                TARGET_BAND, band2, level="ERROR")
            sys.exit(EXIT_FAILED)


        # === Step 4: Validate interface errors ===
        log("=== Step 4: Validating Interface Error Counters ===")

        if not validate_ifconfig_errors(DATA_INTERFACE, THRESHOLD):
            log("TEST FAILED: Interface error threshold exceeded.", level="ERROR")
            sys.exit(EXIT_FAILED)

        log("Interface error validation passed.")

        # Final PASS
        log("=== TEST PASSED — Band lock successful ===")
        sys.exit(EXIT_SUCCESS)


    except Exception as e:
        log("TEST FAILED - Unhandled exception: %s", e, level="ERROR")
        sys.exit(EXIT_FAILED)
