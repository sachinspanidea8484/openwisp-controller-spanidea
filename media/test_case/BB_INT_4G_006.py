# START_DESCRIPTION 
#1. Verify band to which BB is currently attached
#2. Unlock the BB and let it select any available band, ARFCN, PCI 
#3. Verify that the band lock is turned off, the BB detaches from the first band and re-attached to an available band, ARFCN, PCI
# END_DESCRIPTION



#!/usr/bin/env python3
"""
4G BAND UNLOCK  TEST (BB-INT-4G-006)
Dynamic target band input via command-line parameter
python3 BB_INT_4G_006.py CONFIGURATION='{"cellular_interface": "wwan0", "error_threshold_percent":"10"}'
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

    # STEP 1: Get all modem sections from UCI
    stdout, _, rc = run_local_command("uci show network | grep '.device='", allow_fail=True)

    if rc != 0 or not stdout.strip():
        log("No modem entries found in UCI", level="FAIL")
        return None

    # Use a set to avoid duplicate section names
    modem_sections = set()
    for line in stdout.splitlines():
        try:
            # network.Modem1.device='/dev/cdc-wdm0' -> Modem1
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
            # Match based on l3_device (e.g., wwan0)
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

    # log(f"Mapped Interface → {modem_name}")
    # log(f"QMI Device → {qmi_device}")

  
    # STEP 3: Get USB Device Root (Hardware Path)
    qmi_base = os.path.basename(qmi_device)
    # Trace from usbmisc to the physical USB device root
    # For wdm0 -> usb2/2-1 | For wdm1 -> usb6/6-1
    stdout, _, rc = run_local_command(f"readlink -f /sys/class/usbmisc/{qmi_base}/device/..", allow_fail=True)

    if rc != 0 or not stdout.strip():
        log("Failed to determine USB parent path", level="FAIL")
        return None

    usb_device_root = stdout.strip()
    log(f"USB Device Root → {usb_device_root}")

    # STEP 4: Detect AT Port (Using socat for stability)

    stdout, _, rc = run_local_command(f"find {usb_device_root} -name 'ttyUSB*'", allow_fail=True)
    
    at_port = None
    if rc == 0 and stdout:
        potential_ports = sorted([f"/dev/{os.path.basename(p.strip())}" for p in stdout.splitlines() if 'ttyUSB' in p])
        
        for tty_dev in potential_ports:
            # log(f"Probing AT on {tty_dev}...")
            
            probe_cmd = f"echo 'AT' | socat -T 1 - '{tty_dev},raw,echo=0,crnl'"
            resp, _, _ = run_local_command(probe_cmd, allow_fail=True)

            if resp and "OK" in resp:
                at_port = tty_dev
                # log(f"Verified AT Port → {at_port}")
                break

    if not at_port:
        log("No functional AT port detected for this modem", level="WARN")

    # STEP 5: Detect Network Type & Model via QMI
    
    stdout, _, rc = run_local_command(f"qmicli -d {qmi_device} --nas-get-signal-info", allow_fail=True)
    
    network_type = "Unknown"
    if rc == 0 and stdout:
        if re.search(r"5G|NR", stdout, re.IGNORECASE):
            network_type = "5G"
        elif re.search(r"LTE", stdout, re.IGNORECASE):
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


    
def unlock_band():
    log("Unlocking (restoring all default LTE/5G bands)...")
    set_band_config(DEFAULT_BND)
    time.sleep(10)



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='4G BAND UNLOCK TEST (BB-INT-4G-006)')
    parser.add_argument('config', help='Configuration string')
    args = parser.parse_args()

    config = parse_config(args.config)

    CELLULAR_IFACE = config.get('cellular_interface', 'wwan0')
    THRESHOLD = float(config.get('error_threshold_percent', 10))
    
   

     
    log("Starting 4G BAND UNLOCK Test BB-INT-4G-006...")
    
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


        # Pre-check 1: Modem Connection 
        log("=== Pre-check 1: Checking Modem Connection Status ===")

        if not ensure_modem_connected(MODEM_INTERFACE, QMI_DEVICE):
            log("TEST FAILED - Modem failed to connect.", level="ERROR")
            sys.exit(EXIT_FAILED)

        log("Modem connection: OK")


        # Pre-check 2: SIM Status 
        log("=== Pre-check 2: Checking SIM Status ===")

        sim_out, _ = at_cmd("AT+CPIN?")
        sim_status = parse_cpin(sim_out)

        if sim_status != "READY":
            log("TEST FAILED - SIM state invalid: %s", sim_status, level="ERROR")
            sys.exit(EXIT_FAILED)

        log("SIM status: READY")


        # Step 1: Check Current Band Configuration 
        log("=== Step 1: Checking current band configuration ===")

        current = get_band_config()

        if not current:
            log("TEST FAILED - Unable to read current band configuration", level="ERROR")
            sys.exit(EXIT_FAILED)

        # ---------- Case A: Already Unlocked -------------------------
        if current == DEFAULT_BND:

            log("Band configuration is DEFAULT (Unlocked).")

            log("=== Step 2: Validating Interface Error Counters ===")

            if not validate_ifconfig_errors(CELLULAR_IFACE, THRESHOLD):
                log("TEST FAILED: Interface error threshold exceeded.", level="ERROR")
                sys.exit(EXIT_FAILED)

            log("Interface error validation passed.")
            log("=== TEST PASSED — Band Unlock already enabled ===")
            sys.exit(EXIT_SUCCESS)


        # ---------- Case B: Locked → Perform Unlock ------------------
        log("Band lock is ENABLED. Current config: %s", current)

        band1 = verify_current_band()

        if not band1:
            log("Unable to detect current active band", level="ERROR")

        log("Currently attached to Band %s", band1)


        # Step 2: Unlock Band 
        log("=== Step 2: Restoring default unlocked configuration ===")
        unlock_band()
        time.sleep(10)

        # Step 3: Verify Re-Attachment 
        log("=== Step 3: Verifying new active band after unlock ===")

        band2 = verify_current_band()

        if not band2:
            log("TEST FAILED - Unable to detect band after unlock", level="ERROR")
            sys.exit(EXIT_FAILED)

        if band2 == band1:
            log("TEST FAILED — DUT did not change band after unlock.", level="ERROR")
            sys.exit(EXIT_FAILED)

        log("DUT successfully detached from Band %s and reattached to Band %s",
            band1, band2)


        # Step 4: Validate Interface Errors 
        log("=== Step 4: Validating Interface Error Counters ===")

        if not validate_ifconfig_errors(CELLULAR_IFACE, THRESHOLD):
            log("TEST FAILED: Interface error threshold exceeded.", level="ERROR")
            sys.exit(EXIT_FAILED)

        log("Interface error validation passed.")
        log("=== TEST PASSED — Band Unlock successful ===")
        sys.exit(EXIT_SUCCESS)

    except Exception as e:
        log("TEST FAILED - Unhandled exception: %s", e, level="ERROR")
        sys.exit(EXIT_FAILED)
