# START_DESCRIPTION 
#1. Verify band to which BB is currently attached
#2. Perform band lock to set band to a different band
#3. Verify that the BB detaches from the first band and re-attached to the specific band.
# END_DESCRIPTION

#!/usr/bin/env python3
"""
5G BAND LOCK  TEST (BB-INT-5G-006)
Dynamic target band input via command-line parameter
python3 BB-INT-5G-006.py CONFIGURATION='{"cellular_interface": "wwan0", "error_threshold_percent":"10", "LOCK_BAND": "3"}'
"""

import os
import re
import sys
import time
import argparse

from common_helper import (log,run_local_command,parse_config, validate_ifconfig_errors, EXIT_SUCCESS, EXIT_FAILED)

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


# ================= MAIN =================
if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='5G BAND LOCK TEST (BB-INT-5G-006)')
    parser.add_argument('config', help='Configuration string')
    args = parser.parse_args()

    config = parse_config(args.config)

    CELLULAR_IFACE = config.get('cellular_interface', 'wwan0')
    TARGET_BAND = int(config.get('LOCK_BAND', 66))
    THRESHOLD = float(config.get('error_threshold_percent', 10))

  
    log(f"Starting 5G BAND LOCK test (BB-INT-5G-006). Target Band: n{TARGET_BAND}")

    try:
        
        # STEP 1: Modem Info
        info = get_modem_status(CELLULAR_IFACE)
        if not info:
            log("TEST FAILED - Unable to get modem status", level="ERROR")
            sys.exit(EXIT_FAILED)

        QMI_DEVICE = info["qmi_device"]
        MODEM_INTERFACE = info["modem_name"]
        BB_AT_PORT = info["at_port"]
        NETWORK_TYPE = info["network_type"]
        log("Modem Info - QMI Device: %s | Modem Interface: %s",QMI_DEVICE, MODEM_INTERFACE)
        log("AT Port: %s" ,BB_AT_PORT)


        # STEP 2: Ensure Connection
        log("=== STEP 2: Checking Modem Connection ===")
        if not ensure_modem_connected(MODEM_INTERFACE, QMI_DEVICE):
            log("TEST FAILED - Modem not connected", level="ERROR")
            sys.exit(EXIT_FAILED)

      
        # STEP 3: SIM Check
        log("=== STEP 3: Checking SIM Status ===")
        sim_out, _ = at_cmd("AT+CPIN?")
        sim_status = parse_cpin(sim_out)

        if sim_status != "READY":
            log(f"TEST FAILED - SIM state: {sim_status}", level="ERROR")
            sys.exit(EXIT_FAILED)

        # STEP 4: 5G Registration
        log("=== STEP 4: Checking 5G Registration ===")
        reg_out, _ = at_cmd("AT+C5GREG?")
        reg_status = parse_c5greg(reg_out)

        if reg_status not in [1, 5]:
            log("TEST FAILED - Not registered to 5G", level="ERROR")
            sys.exit(EXIT_FAILED)
            
       
        # STEP 5: Current Band
        log("=== STEP 5: Current RAT & Band ===")
        rf_out, _ = at_cmd("AT#RFSTS")
        rf = parse_rfsts_mode_and_band(rf_out)

        log(f"Current RAT={rf['mode']} Band={rf['band']}")
        
        # STEP 5A: Check Current BND Configuration
        log("=== STEP 5A: Checking Band Configuration (Before Lock) ===")

        bnd_before_out, _ = at_cmd("AT#BND?")
        bnd_before = parse_bnd_status(bnd_before_out)

        if not bnd_before:
            log("TEST FAILED - Unable to parse BND status", level="ERROR")
            sys.exit(EXIT_FAILED)

        log(f"BND Status Before Lock: {bnd_before}")

        # STEP 6: Lock Target Band
        log(f"=== STEP 6: Locking NR Band n{TARGET_BAND} ===")
        low, high = band_to_bitmask(TARGET_BAND)

        cmd = (
            f"AT#BND=0,0,"
            f"A7E2BB0F38DF,42,"
            f"{low},{high},"
            f"{low},{high}"
        )

        at_cmd(cmd)

        log(f"Waiting {WAITING_TIME}s for re-attach...")
        time.sleep(WAITING_TIME)
        
      
        # STEP 6A: Verify BND After Lock
        log("=== STEP 6A: Verifying Band Configuration (After Lock) ===")

        bnd_after_out, _ = at_cmd("AT#BND?")
        bnd_after = parse_bnd_status(bnd_after_out)

        if not bnd_after:
            log("TEST FAILED - Unable to parse BND after lock", level="ERROR")
            sys.exit(EXIT_FAILED)

        log(f"BND Status After Lock: {bnd_after}")

        if bnd_after["status"] != "LOCKED":
            log("TEST FAILED - BND still UNLOCKED after lock command", level="ERROR")
            sys.exit(EXIT_FAILED)
            

        if bnd_before == bnd_after:
            log("TEST FAILED - BND configuration did not change", level="ERROR")
            sys.exit(EXIT_FAILED)


        # STEP 7: Verify Attach Band
        log("=== STEP 7: Verifying Attach Band ===")
        max_attempts = 2   # 1 initial try + 1 retry
        attempt = 1
        band_switch_success = False

        while attempt <= max_attempts:
            rf_verify, _ = at_cmd("AT#RFSTS")
            rf_new = parse_rfsts_mode_and_band(rf_verify)
            
            log(f"Attempt {attempt}: RAT={rf_new['mode']} Band={rf_new['band']}")

            # Check if the modem reattached to the target band
            if rf_new["mode"].startswith("NR") and rf_new["band"] == f"n{TARGET_BAND}":
                band_switch_success = True
                log("Band reattachment successful.")
                break  # Exit loop if successful
            else:
                log(f"Band not reattached to target on attempt {attempt}, retrying..." if attempt < max_attempts else "No more retries left")
                attempt += 1

        if not band_switch_success:
            log("TEST FAILED — Band not reattached to target after retries", level="ERROR")
            sys.exit(EXIT_FAILED)


        # STEP 8: Validate Interface Errors
        log("=== STEP 8: Validating Interface Error Counters ===")

        if not validate_ifconfig_errors(CELLULAR_IFACE, THRESHOLD):
            log("TEST FAILED: Interface error threshold exceeded.", level="ERROR")
            sys.exit(EXIT_FAILED)

        log("Interface error validation passed.")

        # FINAL RESULT
        
        log("=== TEST PASSED — 5G Band Lock successful ===")
        sys.exit(EXIT_SUCCESS)

    except Exception as e:
        log("TEST FAILED - Unhandled exception: %s", e, level="ERROR")
        sys.exit(EXIT_FAILED)
