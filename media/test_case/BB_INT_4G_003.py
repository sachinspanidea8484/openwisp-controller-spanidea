import re
import sys
import time
import subprocess
from datetime import datetime

# === CONFIGURATION ===
BB_AT_PORT = "/dev/ttyUSB3"
BB_QMI_DEVICE = "/dev/cdc-wdm0"
LOG_FILE = "BB_INT_4G_003_LOCK.log"

# === EXIT CODES ===
EXIT_SUCCESS = 0
EXIT_FAILED = 1
EXIT_PRECONDITION_FAILED = 2
EXIT_CMDS_NON_RESPONSIVE = 3

# === GLOBAL ===
MAX_RETRIES = 3

# === LOGGING ===
def timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log(message):
    line = f"[+] {timestamp()} - {message}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

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
    return run_cmd(f"echo -e '{cmd}\\r' | socat - {BB_AT_PORT},raw,echo=0,crnl")

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

# === Helpers ===
def ensure_modem_connected():
    log("Checking modem connection status...")
    for attempt in range(1, MAX_RETRIES + 1):
        status_out, _ = run_cmd(f"uqmi -d {BB_QMI_DEVICE} --get-data-status")
        if "connected" in status_out:
            log("Modem is connected.")
            return True
        log(f"Attempt {attempt}/{MAX_RETRIES}: Modem disconnected, retrying...")
        run_cmd("ifup Modem1 && ifup Modem2")
        time.sleep(60)
    return False

# === Main Script ===
def main():
    log("===Starting 4G PCI LOCK Test BB-INT-4G-003===")

    # Step 1: Check SIM
    log("===Check SIN status====")
    sim_out, _ = at_cmd("AT+CPIN?")
    sim_status = parse_cpin(sim_out)
    if sim_status == "NOT_INSERTED":
        log("TEST FAILED!!! :- SIM not inserted. Aborting.")
        sys.exit(EXIT_PRECONDITION_FAILED)
    elif sim_status == "PIN_REQUIRED":
        log("TEST FAILED!!! :- SIM requires PIN. Aborting.")
        sys.exit(EXIT_PRECONDITION_FAILED)
    elif sim_status == "PUK_REQUIRED":
        log("TEST FAILED!!! :- SIM requires PUK. Aborting.")
        sys.exit(EXIT_PRECONDITION_FAILED)
    elif sim_status == "READY":
        log("SIM is ready.")
    else:
        log(f"TEST FAILED!!! :- Unknown SIM state: {sim_out}")
        sys.exit(EXIT_PRECONDITION_FAILED)

    # Step 2: Ensure modem is connected
    log("===Checking modem connection status====")
    #while True:
    if ensure_modem_connected():
         log("Modem connection established successfully.")
         #break
    else:
         log("TEST FAILED!!!:- Modem failed to connect after max retries")
         sys.exit(EXIT_PRECONDITION_FAILED)
          

    # Step 3: Packet domain attach (retry loop)
    log("===Checking Packet domain attach Info====")
    for attempt in range(MAX_RETRIES):
        cgatt_out, _ = at_cmd("AT+CGATT?")
        attached = parse_cgatt(cgatt_out)
        if attached:
            log("Attached to packet domain.")
            break
        else:
            log(f"Not attached to packet domain (attempt {attempt+1}), retrying...")
            time.sleep(5)
    else:
        log("TEST FAILED!!!:- Failed to attach to packet domain after retries.")
        sys.exit(EXIT_PRECONDITION_FAILED)

    # Step 4: Check 4G Registration
    log("===Checking Registration Status====")
    nw_status_out, _ = at_cmd("AT+CEREG?")
    reg_status = parse_cereg(nw_status_out)
    if reg_status in [1, 5]:
        log(f"Registered to 4G network ({'Home' if reg_status == 1 else 'Roaming'})")
    else:
        log(f"TEST FAILED!!!:- Not registered to 4G network. CEREG status: {reg_status}")
        sys.exit(EXIT_PRECONDITION_FAILED)

    # Step 5: PDP context
    log("===Checking PDP context====")
    pdp_out, _ = at_cmd("AT+CGCONTRDP")
    log("PDP Context Info:")
    log(pdp_out or " No PDP context configured.")

    # Step 6: Check PCI Lock state
    log("===Checking PCI Lock state====")
    bcchlock_out, _ = at_cmd("AT#BCCHLOCK?")
    bcch_status = parse_bcchlock(bcchlock_out)
    if bcch_status:
        if bcch_status["lock_enabled"]:
            log(f"TEST FAILED!!!:- PCI Lock ENABLED: EARFCN={bcch_status['earfcn']}, PCI={bcch_status['pci']} (0x{bcch_status['pci']:X})")
            sys.exit(EXIT_PRECONDITION_FAILED)
        else:
            log("PCI Lock DISABLED.")
    else:
        log("TEST FAILED!!!:- Could not parse BCCHLOCK response.")
        sys.exit(EXIT_PRECONDITION_FAILED)

    # Step 7: Get current LTE serving cell
    log("===Checking Get current LTE serving cell====")
    lteds_out, _ = at_cmd("AT#LTEDS")
    current = parse_lteds(lteds_out)
    if not current:
        log("TEST FAILED!!!:- Failed to parse LTEDS info.")
        sys.exit(EXIT_CMDS_NON_RESPONSIVE)

    log(f"Current LTE: EARFCN={current['earfcn']}, CELLID={current['cellid']} (0x{current['cellid']:X}), PCI={current['pci']} (0x{current['pci']:X})")

    # Step 8: Apply PCI Lock
    log("===Applying PCI Lock====")
    bcch_cmd = f"AT#BCCHLOCK=1024,0,65535,{current['earfcn']},{current['pci']:X}"
    at_cmd(bcch_cmd)

    # Step 9: Verify lock settings
    log("===Veritying Lock setting====")
    bcchlock_verify_out, _ = at_cmd("AT#BCCHLOCK?")
    bcch_status = parse_bcchlock(bcchlock_verify_out)
    if bcch_status and bcch_status["lock_enabled"] and \
       bcch_status["earfcn"] == current["earfcn"] and bcch_status["pci"] == current["pci"]:
        log(f"PCI Lock successfully set: EARFCN={bcch_status['earfcn']}, PCI={bcch_status['pci']} (0x{bcch_status['pci']:X})")
    else:
        log("TEST FAILED!!!:- PCI Lock settings do not match after setting. TEST FAILED.")
        sys.exit(EXIT_FAILED)

    # Step 10: Final LTE serving cell check
    log("===Checking final serving cell info====")
    lteds_post_out, _ = at_cmd("AT#LTEDS")
    locked = parse_lteds(lteds_post_out)
    if locked and locked["earfcn"] == current["earfcn"] and locked["pci"] == current["pci"]:
        log(f"Lock Verified on network: EARFCN={locked['earfcn']}, PCI={locked['pci']} (0x{locked['pci']:X})")
        log("TEST PASSED !!!!")
        sys.exit(EXIT_SUCCESS)
    else:
        log("TEST FAILED!!!:- Network serving cell does not match locked EARFCN/PCI.")
        sys.exit(EXIT_FAILED)

if __name__ == "__main__":
    main()

