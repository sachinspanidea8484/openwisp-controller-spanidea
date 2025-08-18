import re
import sys
import time
import subprocess
from datetime import datetime

# === CONFIGURATION ===
BB_AT_PORT = "/dev/ttyUSB3"
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

# === AT Command Execution ===
def run_at_command(cmd):
    log(f"[CMD] {cmd}")
    try:
        full_cmd = f"echo -e '{cmd}\\r' | socat - {BB_AT_PORT},raw,echo=0,crnl"
        log(f"Executing command: {full_cmd}")
        output = subprocess.check_output(full_cmd, shell=True, stderr=subprocess.STDOUT, timeout=20).decode().strip()
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

def parse_csurv_neighbors(output, current_earfcn, current_cellid, current_pci):
    neighbors = []
    for match in re.finditer(r"earfcn:\s*(\d+).*?cellId:\s*(\d+).*?phyCellId:\s*(\d+)", output, re.DOTALL):
        earfcn = int(match.group(1))
        cellid = int(match.group(2))
        pci = int(match.group(3))
        if earfcn != current_earfcn or cellid != current_cellid or pci != current_pci:
            neighbors.append({"earfcn": earfcn, "cellid": cellid, "pci": pci})
    return neighbors

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
    
     # Step 2: PDP context
    pdp_output = run_at_command("AT+CGDCONT?")
    log("PDP Context Info:")
    log(pdp_output or " No PDP context configured.")

    # Step 3: Packet domain attach
    cgatt_output = run_at_command("AT+CGATT?")
    if "+CGATT: 1" in cgatt_output:
        log("Attached to packet domain.")
    else:
        log("Not attached to packet domain.")
        sys.exit(EXIT_PRECONDITION_FAILED)

    # Step 3: Check 4G Registration
    nw_status_output = run_at_command("AT+CEREG?")
    reg_status = parse_cereg(nw_status_output)
    if reg_status in [1, 5]:
        log(f"Registered to 4G network ({'Home' if reg_status == 1 else 'Roaming'})")
    else:
        log(f"Not registered to 4G network. CEREG status: {reg_status}")
        sys.exit(EXIT_PRECONDITION_FAILED)

    # Step 4: Check PCI Lock
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

    # Step 4: Get current LTE cell
    lteds_output = run_at_command("AT#LTEDS")
    current = parse_lteds(lteds_output)
    if not current:
        log("Failed to parse LTEDS info.")
        sys.exit(EXIT_CMDS_NON_RESPONSIVE)

    log(f"Current LTE: EARFCN={current['earfcn']}, CELLID={current['cellid']} (0x{current['cellid']:X}), PCI={current['pci']} (0x{current['pci']:X})")

    # Step 5: Scan neighbors with retry
    log("Scanning neighbors...")
    neighbors = []
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        csurv_output = run_at_command("AT#CSURV")
        time.sleep(30)
        neighbors = parse_csurv_neighbors(csurv_output, current['earfcn'], current['cellid'], current['pci'])

        if neighbors:
            log(f"Found {len(neighbors)} neighbor cells on attempt {attempt}")
            break
        else:
            log(f"No neighbor cells found on attempt {attempt}. Retrying in 10s...")
            time.sleep(10)

    if not neighbors:
        log("No neighbor cells found after retries. Aborting.")
        sys.exit(EXIT_CMDS_NON_RESPONSIVE)

    # Step 6: Pick neighbor
    chosen = next((n for n in neighbors if n['earfcn'] < current['earfcn'] or n['cellid'] < current['cellid']), None)
    if not chosen:
        log("No suitable neighbor found.")
        sys.exit(EXIT_CMDS_NON_RESPONSIVE)

    log(f"Chosen Neighbor: EARFCN={chosen['earfcn']}, CELLID={chosen['cellid']} (0x{chosen['cellid']:X}), PCI={chosen['pci']} (0x{chosen['pci']:X})")

    # Step 7: Lock to chosen neighbor
    bcch_cmd = f"AT#BCCHLOCK=1024,0,65535,{chosen['earfcn']},{chosen['pci']:X}"
    run_at_command(bcch_cmd)

    # Step 8: Reboot BB
    run_at_command("AT#ENHRST=1,0")
    log("Rebooting... Waiting 90s")
    time.sleep(90)

    # Step 9: Confirm PCI Lock after reboot
    bcchlock_status_output = run_at_command("AT#BCCHLOCK?")
    bcch_status = parse_bcchlock(bcchlock_status_output)
    if bcch_status and bcch_status["lock_enabled"]:
        log(f"PCI Lock after reboot: EARFCN={bcch_status['earfcn']}, PCI={bcch_status['pci']} (0x{bcch_status['pci']:X})")
    else:
        log("PCI Lock not active after reboot.")

    # Step 10: Final cell validation
    lteds_output_post = run_at_command("AT#LTEDS")
    locked = parse_lteds(lteds_output_post)
    if locked and locked['earfcn'] == chosen['earfcn'] and locked['cellid'] == chosen['cellid'] and locked['pci'] == chosen['pci']:
        log(f"Lock Verified: EARFCN={locked['earfcn']}, CELLID={locked['cellid']} (0x{locked['cellid']:X}), PCI={locked['pci']} (0x{locked['pci']:X})")
        log(f"TEST PASSED!!!!!")
        sys.exit(EXIT_SUCCESS)

    else:
        log("PCI Lock Mismatch after reboot.")
        if locked:
            log(f"Post-reboot LTE: EARFCN={locked['earfcn']}, CELLID={locked['cellid']}, PCI={locked['pci']}")
        log("TEST FAILED!!!!!")
        sys.exit(EXIT_FAILED)

    log("4G PCI LOCK TEST COMPLETE.")

if __name__ == "__main__":
    main()

