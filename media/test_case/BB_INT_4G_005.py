#!/usr/bin/env python3
"""
4G BAND LOCK TEST (BB-INT-4G-005)
Dynamic target band input via command-line parameter
python3 BB_INT_4G_005.py CONFIGURATION='{"LOCK BAND": "66"}'
"""

import re
import sys
import time
import json
import argparse
import subprocess
from datetime import datetime
 
 
def parse_config(config_str):
    """Parse CONFIGURATION=... style string into a Python dict"""
 
    # Remove 'CONFIGURATION=' prefix if present
    if config_str.startswith("CONFIGURATION="):
        config_str = config_str[len("CONFIGURATION="):]
 
    # Try to parse the remaining string as JSON
    try:
        return json.loads(config_str)
    except json.JSONDecodeError as e:
        print(f"Error parsing CONFIGURATION JSON: {e}", file=sys.stderr)
        return {}


# === CONFIGURATION ===
BB_AT_PORT = "/dev/ttyUSB3"
BB_QMI_DEVICE = "/dev/cdc-wdm0"
LOG_FILE = "BB_INT_4G_005.log"

# === EXIT CODES ===
EXIT_SUCCESS = 0
EXIT_FAILED = 1
EXIT_PRECONDITION_FAILED = 2
EXIT_CMDS_NON_RESPONSIVE = 3

# === CONSTANTS ===
DEFAULT_BND = ["0", "22", "A7E2BB0F38DF", "42", "1A0290828D7", "7042", "81A03B0A38D7", "7C42"]
WAITING_TIME = 120  # seconds
MAX_RETRIES = 3

# === LOGGING ===
def timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log(message):
    line = f"[+] {timestamp()} - {message}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

# === SHELL HELPER ===
def run_cmd(command):
    log(f"Executing command: {command}")
    try:
        result = subprocess.run(
            command, shell=True, text=True, capture_output=True, check=False
        )
        output = result.stdout.strip()
        error = result.stderr.strip()
        if output:
            log(f"Output: {output}")
        if error:
            log(f"Error: {error}")
        return output, error
    except Exception as e:
        log(f"Command execution failed: {e}")
        return "", str(e)

# === AT Command Helper ===
def at_cmd(cmd):
    """Send AT command to modem via socat"""
    return run_cmd(f"echo -e '{cmd}\\r' | socat - {BB_AT_PORT},raw,echo=0,crnl")


# === PARSERS ===
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

def unlock_band():
    log("Unlocking (restoring all default LTE/5G bands)...")
    set_band_config(DEFAULT_BND)
    time.sleep(5)
    verify_current_band()

# === MAIN ===
if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='4G BAND LOCK TEST (BB-INT-4G-005)')
    parser.add_argument('config', help='Configuration string')
 
    args = parser.parse_args()
 
    # Parse configuration
    config = parse_config(args.config)
 
    # Access by key and print
    TARGET_BAND = config.get('LOCK BAND', config.get('LOCK_BAND', '66'))
 
    print(f"TARGET_BAND : {TARGET_BAND}")
    
    log(f"=== Starting 4G BAND LOCK (BB-INT-5G-005) Test with target band {TARGET_BAND} ===")

    try:
        log("=== STEP 1: Checking SIM status ===")
        sim_out, _ = at_cmd("AT+CPIN?")
        sim_status = parse_cpin(sim_out)
        if sim_status != "READY":
            log(f"TEST FAILED: SIM not ready ({sim_status}). Aborting.")
            sys.exit(EXIT_PRECONDITION_FAILED)
        log("SIM is ready.")

        log("=== STEP 2: Checking 4G Network (Operator + RAT) ===")
        cops_out, _ = at_cmd("AT+COPS?")
        info = parse_cops(cops_out)
        if info:
            log(f"Operator: {info['operator']} | RAT: {info['act_name']} (Code {info['act_code']})")
        else:
            log("Could not parse AT+COPS? output.")
            
        log("=== STEP 3: Check packet domain attach ===")
        for attempt in range(MAX_RETRIES):
            cgatt_out, _ = at_cmd("AT+CGATT?")
            attached = parse_cgatt(cgatt_out)
            if attached:
                log("Attached to packet domain.")
                break
            log(f"Retrying packet domain attach ({attempt+1})...")
            time.sleep(5)
        else:
            log("Failed to attach to packet domain.")
            sys.exit(EXIT_PRECONDITION_FAILED)

        log("=== STEP 4: Check registration status ===")
        nw_status_out, _ = at_cmd("AT+CEREG?")
        reg_status = parse_cereg(nw_status_out)
        if reg_status not in [1, 5]:
            log(f"Not registered to 4G network (CEREG={reg_status}).")
            sys.exit(EXIT_PRECONDITION_FAILED)
        log(f"Registered to 4G network ({'Home' if reg_status == 1 else 'Roaming'})")

        log("=== STEP 5: Band operations ===")
        log("*** Step 5(I): Check current active band ***")
        band1 = verify_current_band()

        log(f"*** Step 5(II): Lock to LTE band {TARGET_BAND} ***")
        lock_band(TARGET_BAND)

        log(f"*** Step 5(III): Waiting {WAITING_TIME}s for network reacquisition ***")
        time.sleep(WAITING_TIME)

        log("*** Step 5(IV): Verify current band after locking ***")
        band2 = verify_current_band()

        if band2 == TARGET_BAND:
            log(f"BB successfully detached from Band {band1} and reattached to specific Band {TARGET_BAND}")
            log("TEST PASSED!!! — Band lock successful.")
            sys.exit(EXIT_SUCCESS)
        else:
            log(f"TEST FAILED!!! — Expected Band {TARGET_BAND} but still on Band {band2}")
            sys.exit(EXIT_FAILED)

    except Exception as e:
        log(f"TEST FAILED - Exception: {e}")
        sys.exit(EXIT_FAILED)


