# START_DESCRIPTION 
#1. Verify band to which BB is currently attached
#2. Perform band lock to set band to a different band
#3. Verify that the BB detaches from the first band and re-attached to the specific band.
# END_DESCRIPTION


#!/usr/bin/env python3
"""
4G BAND LOCK  TEST (BB-INT-4G-005)
Dynamic target band input via command-line parameter
python3 BB-INT-4G-005.py CONFIGURATION='{"cellular_interface": "wwan0", "error_threshold_percent":"10", "LOCK_BAND": "66"}'
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



def get_modem_status(interface):
    log(f"Getting modem full status for {interface}...")

    # Modem sections
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

    # interface -> modem
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

    qmi_base = os.path.basename(qmi_device)
    stdout, _, rc = run_local_command(f"readlink -f /sys/class/usbmisc/{qmi_base}/device/..", allow_fail=True)

    if rc != 0 or not stdout.strip():
        log("Failed to determine USB parent path", level="FAIL")
        return None

    usb_device_root = stdout.strip()

    stdout, _, rc = run_local_command(f"find {usb_device_root} -maxdepth 2 -name 'ttyUSB*'", allow_fail=True)
    
    at_port = None
    if rc == 0 and stdout:
        unique_ports = {f"/dev/{os.path.basename(p.strip())}" for p in stdout.splitlines() if 'ttyUSB' in p}
        potential_ports = sorted(list(unique_ports))
        
        for tty_dev in potential_ports:
            probe_cmd = f"echo 'AT' | socat -T 1 - '{tty_dev},raw,echo=0,crnl'"
            resp, _, _ = run_local_command(probe_cmd, allow_fail=True)

            if resp and "OK" in resp:
                at_port = tty_dev
                break

    if not at_port:
        log("No functional AT port detected", level="WARN")

    # Detect Network Type 
    stdout, _, rc = run_local_command(f"qmicli -d {qmi_device} --nas-get-signal-info", allow_fail=True)
    
    network_type = "No Signal"
    if rc == 0 and stdout:
      
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

    CELLULAR_IFACE = config.get('cellular_interface', 'wwan0')
    TARGET_BAND = int(config.get('LOCK_BAND', 66))
    THRESHOLD = float(config.get('error_threshold_percent', 10))
    
  
     
    log(f"Starting 4G BAND LOCK Test BB-INT-4G-005 with target band {TARGET_BAND}...")
    
    try:
        info = get_modem_status(CELLULAR_IFACE)

        if not info:
            log("TEST FAILED - Failed to get modem status", level="ERROR")
            sys.exit(EXIT_FAILED)

        QMI_DEVICE = info["qmi_device"]
        MODEM_INTERFACE = info["modem_name"]
        BB_AT_PORT = info["at_port"]
        NETWORK_TYPE = info["network_type"]

        log("Modem Info - QMI Device: %s | Modem Interface: %s | Network Type: %s",
            QMI_DEVICE, MODEM_INTERFACE, NETWORK_TYPE)
        log("AT Port: %s" ,BB_AT_PORT)

         # === Pre-check 1: Modem Connection ===
        log("=== Pre-check 1: Checking Modem Connection Status ===")
        if not ensure_modem_connected(MODEM_INTERFACE, QMI_DEVICE):
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

      
        log("TEST PASSED: Band lock successful")
        sys.exit(EXIT_SUCCESS)


    except Exception as e:
        log("TEST FAILED - Unhandled exception: %s", e, level="ERROR")
        sys.exit(EXIT_FAILED)
