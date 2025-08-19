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

# === LOGGING ===
def timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log(msg):
    line = f"[+] {timestamp()} - {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

# === Local command execution ===
def run_local_cmd(command):
    log(f"Executing local command: {command}")
    try:
        output = subprocess.check_output(
            command, shell=True, stderr=subprocess.STDOUT
        ).decode().strip()
        if output:
            log(f"Output: {output}")
        return output
    except subprocess.CalledProcessError as e:
        log(f"Error: {e.output.decode().strip()}")
        return ""

# === AT Command Execution ===
def run_at_command(cmd):
    log(f"[CMD] {cmd}")
    try:
        full_cmd = f"echo -e '{cmd}\\r' | socat - {BB_AT_PORT},raw,echo=0,crnl"
        output = subprocess.check_output(
            full_cmd, shell=True, stderr=subprocess.STDOUT, timeout=20
        ).decode().strip()
        log(f"[OUT] {output}")
        time.sleep(1)
        return output
    except subprocess.TimeoutExpired:
        log(f"[ERROR] Timeout while running: {cmd}")
        return ""
    except subprocess.CalledProcessError as e:
        log(f"[ERROR] Command failed: {cmd} -- {e.output.decode().strip()}")
        return ""

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
        return {
            "earfcn": earfcn,
            "pci": pci,
            "lock_enabled": lock_enabled
        }
    return None

def parse_cereg(output):
    match = re.search(r"\+CEREG:\s*\d+,(\d+)", output)
    if match:
        return int(match.group(1))
    return None

# === Ensure modem connection ===
def ensure_modem_connected():
    log("Checking modem connection status...")
    status_out = run_local_cmd(f"uqmi -d {BB_QMI_DEVICE} --get-data-status")
    if "disconnected" in status_out:
        log("Modem disconnected. Bringing up interface...")
        run_local_cmd("ifup Modem1")
        time.sleep(15)
        status_out = run_local_cmd(f"uqmi -d {BB_QMI_DEVICE} --get-data-status")
        if "disconnected" in status_out:
            log("Failed to connect modem.")
            return False
    log("Modem is connected.")
    return True

# === Main Script ===
def main():
    log("Starting 4G PCI Lock Test...")

    # Step 1: Check SIM
    sim_status = run_at_command("AT+CPIN?")
    if "+CME ERROR: 10" in sim_status:
        log("SIM not inserted. Aborting.")
        sys.exit(EXIT_PRECONDITION_FAILED)
    elif "+CPIN: SIM PIN" in sim_status:
        log("SIM requires PIN. Aborting.")
        sys.exit(EXIT_PRECONDITION_FAILED)
    elif "READY" in sim_status:
        log("SIM is ready.")
    else:
        log(f"Unknown SIM state: {sim_status}")
        sys.exit(EXIT_PRECONDITION_FAILED)

    # Step 2: Ensure modem is connected (loop until success)
    while True:
        if ensure_modem_connected():
            log("Modem connection established successfully.")
            break
        else:
            log("Retrying modem connection in 30 seconds...")
            time.sleep(30)

    # Step 3: Packet domain attach
    cgatt_output = run_at_command("AT+CGATT?")
    if "+CGATT: 1" in cgatt_output:
        log("Attached to packet domain.")
    else:
        log("Not attached to packet domain.")
        sys.exit(EXIT_PRECONDITION_FAILED)

    # Step 4: Check 4G Registration
    nw_status_output = run_at_command("AT+CEREG?")
    reg_status = parse_cereg(nw_status_output)
    if reg_status in [1, 5]:
        log(f"Registered to 4G network ({'Home' if reg_status == 1 else 'Roaming'})")
    else:
        log(f"Not registered to 4G network. CEREG status: {reg_status}")
        sys.exit(EXIT_PRECONDITION_FAILED)

    # Step 5: PDP context
    pdp_output = run_at_command("AT+CGCONTRDP")
    log("PDP Context Info:")
    log(pdp_output or " No PDP context configured.")

    # Step 6: Check PCI Lock state
    bcchlock_status_output = run_at_command("AT#BCCHLOCK?")
    bcch_status = parse_bcchlock(bcchlock_status_output)
    if bcch_status:
        if bcch_status["lock_enabled"]:
            log(f"PCI Lock ENABLED: EARFCN={bcch_status['earfcn']}, PCI={bcch_status['pci']} (0x{bcch_status['pci']:X})")
            sys.exit(EXIT_PRECONDITION_FAILED)
        else:
            log("PCI Lock DISABLED.")
    else:
        log("Could not parse BCCHLOCK response.")
        sys.exit(EXIT_PRECONDITION_FAILED)

    # Step 7: Get current LTE serving cell
    lteds_output = run_at_command("AT#LTEDS")
    current = parse_lteds(lteds_output)
    if not current:
        log("Failed to parse LTEDS info.")
        sys.exit(EXIT_CMDS_NON_RESPONSIVE)

    log(f"Current LTE: EARFCN={current['earfcn']}, CELLID={current['cellid']} (0x{current['cellid']:X}), PCI={current['pci']} (0x{current['pci']:X})")

    # Step 8: Apply PCI Lock
    bcch_cmd = f"AT#BCCHLOCK=1024,0,65535,{current['earfcn']},{current['pci']:X}"
    run_at_command(bcch_cmd)

    # Step 9: Verify lock settings
    bcchlock_status_output = run_at_command("AT#BCCHLOCK?")
    bcch_status = parse_bcchlock(bcchlock_status_output)
    if bcch_status and bcch_status["lock_enabled"] and \
       bcch_status["earfcn"] == current["earfcn"] and bcch_status["pci"] == current["pci"]:
        log(f"PCI Lock successfully set: EARFCN={bcch_status['earfcn']}, PCI={bcch_status['pci']} (0x{bcch_status['pci']:X})")
    else:
        log("PCI Lock settings do not match after setting. TEST FAILED.")
        sys.exit(EXIT_FAILED)

    # Step 10: Final LTE serving cell check
    lteds_output_post = run_at_command("AT#LTEDS")
    locked = parse_lteds(lteds_output_post)
    if locked and locked["earfcn"] == current["earfcn"] and locked["pci"] == current["pci"]:
        log(f"Lock Verified on network: EARFCN={locked['earfcn']}, PCI={locked['pci']} (0x{locked['pci']:X})")
        log("TEST PASSED !!!!")
        sys.exit(EXIT_SUCCESS)
    else:
        log("Network serving cell does not match locked EARFCN/PCI.")
        sys.exit(EXIT_FAILED)

if __name__ == "__main__":
    main()