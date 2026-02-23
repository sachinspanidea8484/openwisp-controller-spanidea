# START_DESCRIPTION 
#1. Initialize logging .
#2. Check the DUT connection and SIM status
#3. Check 5G Network Registration status.
#4. Check PCI/Cell Lock status.
#5. Selecting the appropriate EARFCN, physical cell id. 
#6. Lock the selected EARFCN and physical cell id.
#7. Verify that the DUT attached to the specified cell.

# END_DESCRIPTION

#!/usr/bin/env python3
"""
5G PCI LOCK  TEST (BB-INT-5G-004)
Dynamic target band input via command-line parameter
python3 BB_INT_5G_004.py CONFIGURATION='{"cellular_interface": "wwan1", "error_threshold_percent":"10"}'
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

    # log(f"Mapped Interface : {modem_name}")
    # log(f"QMI Device : {qmi_device}")

  
    # STEP 3: Get USB Device Root (Hardware Path)
    qmi_base = os.path.basename(qmi_device)
    # Trace from usbmisc to the physical USB device root
    # For wdm0 -> usb2/2-1 | For wdm1 -> usb6/6-1
    stdout, _, rc = run_local_command(f"readlink -f /sys/class/usbmisc/{qmi_base}/device/..", allow_fail=True)

    if rc != 0 or not stdout.strip():
        log("Failed to determine USB parent path", level="FAIL")
        return None

    usb_device_root = stdout.strip()
    # log(f"USB Device Root : {usb_device_root}")

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
                log(f"Verified AT Port: {at_port}")
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

    parser = argparse.ArgumentParser(description='5G PCI LOCK TEST (BB-INT-4G-004)')
    parser.add_argument('config', help='Configuration string')
    args = parser.parse_args()

    config = parse_config(args.config)

    CELLULAR_IFACE = config.get('cellular_interface', 'wwan0')
    THRESHOLD = float(config.get('error_threshold_percent', 10))
    

     
    log("Starting 5G PCI LOCK Test BB-INT-4G-004...")
    
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



        # Step 3: 5G Registration
        log("=== Step 3: Checking 5G Registration Status ===")
        reg_output,_ = at_cmd("AT+C5GREG?")
            
        reg_status = parse_c5greg(reg_output)
        if reg_status in [1, 5]:
            log(f"Registered to 5G ({'Home' if reg_status == 1 else 'Roaming'})")
        else:
            log(f"Not registered to 5G. C5GREG: {reg_status}")
            sys.exit(EXIT_FAILED)



        # Step 4: PCI lock status
        log("=== Step 4: Verifying PCI Unlock ===")
        lock_output,_ = at_cmd("AT#5GBCCHLOCK?")
            
        pci_lock_status = get_pci_lock_status(lock_output)
        log(f"PCI Lock is currently: {pci_lock_status}")

        if pci_lock_status["status"] == "ENABLED":
            log("PCI Lock already ENABLED. Exiting.")
            sys.exit(EXIT_FAILED)

        # Step 4(a): Current NR cell
        nrds_out, _ = at_cmd("AT#NRDS")       
        current = parse_nrds(nrds_out)
        if not current:
            log("Failed to parse NRDS.")
            sys.exit(EXIT_FAILED)

        log(
            f"Current NR Cell → "
            f"BAND={current['band']}, "
            f"ARFCN={current['arfcn']}, "
            f"PCI={current['pci']}, "
            f"SCS={current['scs']}"
        )

        # Step 5: Apply PCI lock
        log("=== Step 5: Applying PCI Lock ===")
        lock_cmd = (
            f"AT#5GBCCHLOCK=0,"
            f"{current['scs']},"
            f"{current['arfcn']},"
            f"{current['pci']},"
            f"{current['band']}"
        )
        lock_status,_ =at_cmd(lock_cmd)
        
        # Step 6: Verify lock config
        log("=== Step 6: Verifying PCI Lock Settings ===")
        lock_verify_out, _ = at_cmd("AT#5GBCCHLOCK?")
        lock_info = get_pci_lock_status(lock_verify_out)


        if lock_info["status"] == "DISABLED":
            log("TEST FAILED!!- PCI Lock is DISABLED.")
            sys.exit(EXIT_FAILED)

        log(f"PCI LOCK ENABLED → {lock_info}")

        # Step 7: Verify NR attachment (with retry)
        log("=== Step 7: Verifying attachment to locked cell ===")

        max_attempts = 2   # 1 initial + 1 retry
        attempt = 1
        success = False
        observed = None

        while attempt <= max_attempts:

            log(f"Verification attempt {attempt}/{max_attempts}...")
            time.sleep(10)

            nrds_out, _ = at_cmd("AT#NRDS")

            if nrds_out:
                log("NR Cell Status:\n%s", nrds_out)

            observed = parse_nrds(nrds_out)

            if not observed:
                log("Failed to parse NRDS output.")
                attempt += 1
                continue

            log(
                f"Observed → "
                f"BAND={observed['band']}, "
                f"ARFCN={observed['arfcn']}, "
                f"PCI={observed['pci']}, "
                f"SCS={observed['scs']}"
            )

            if (
                observed["band"] == current["band"] and
                observed["arfcn"] == current["arfcn"] and
                observed["pci"] == current["pci"] and
                observed["scs"] == current["scs"]
            ):
                success = True
                break

            log("Mismatch detected. Retrying...")
            attempt += 1


        # ================= FINAL DECISION =================
        if success:

            log("PCI LOCK SUCCESSFUL.")
            log("=== Step 8: Validating Interface Error Counters ===")

            if not validate_ifconfig_errors(CELLULAR_IFACE, THRESHOLD):
                log("TEST FAILED: Interface error threshold exceeded.", level="ERROR")
                sys.exit(EXIT_FAILED)

            log("Interface error validation passed.")
            log("=== TEST PASSED — PCI Lock successful ===")
            sys.exit(EXIT_SUCCESS)

        # -------- Failure Case -----------------------------

        log("TEST FAILED!! PCI LOCK FAILED.")

        log(
            f"Expected → "
            f"BAND={current['band']}, "
            f"ARFCN={current['arfcn']}, "
            f"PCI={current['pci']}, "
            f"SCS={current['scs']} | "
            f"Observed → {observed}"
        )

        sys.exit(EXIT_FAILED)



    except Exception as e:
        log("TEST FAILED - Unhandled exception: %s", e, level="ERROR")
        sys.exit(EXIT_FAILED)