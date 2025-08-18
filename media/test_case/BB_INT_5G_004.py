import re
import time
from datetime import datetime
import sys
import subprocess

# === CONFIGURATION ===
BB_AT_PORT = "/dev/ttyUSB3"
LOG_FILE = "BB_INT_5G_004_LOCK.log"

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

# === AT Command Execution (Local) ===
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

# === PARSERS ===
def parse_c5greg(output):
    match = re.search(r"\+C5GREG:\s*\d+,(\d+)", output)
    return int(match.group(1)) if match else None

def parse_nrds(output):
    match = re.search(r"#NRDS:\s*(\d+)/[^,]*,[^,]*,(\d+),(\d+),.*?,.*?,.*?,.*?,.*?,.*?,.*?/.*?,.*?/.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,(\d+)", output)
    if match:
        return {
            "band": int(match.group(1)),
            "arfcn": int(match.group(2)),
            "pci": int(match.group(3)),
            "scs": int(match.group(4))
        }
    return None

def parse_csurv_neighbors(output):
    neighbors = []
    for match in re.finditer(
        r"nr_arfcn:\s*(\d+)\s+nr_band:\s*(\d+)\s+nr_scs:\s*(\d+)\s+nr_mcc:.*?nr_mnc:.*?cell_id:\s*(\d+).*?pci:\s*(\d+)",
        output,
        re.DOTALL
    ):
        neighbors.append({
            "arfcn": int(match.group(1)),
            "band": int(match.group(2)),
            "scs": int(match.group(3)),
            "cell_id": int(match.group(4)),
            "pci": int(match.group(5))
        })
    return neighbors

def get_pci_lock_status(output):
    match = re.search(r"#5GBCCHLOCK:\s*(\d+)", output)
    if match:
        value = match.group(1).strip()
        if value in ["0", "1"]:
            return "ENABLED"
        elif value == "2":
            return "DISABLED"
    return "UNKNOWN"

# === MAIN ===
def main():
    log("Starting 5G PCI Lock Test...")

    # Step 1: Check SIM
    sim_status = run_at_command("AT+CPIN?")
    if "+CME ERROR: 10" in sim_status:
        log("SIM not inserted.")
        sys.exit(EXIT_PRECONDITION_FAILED)
    elif "+CPIN: SIM PIN" in sim_status:
        log("SIM requires PIN.")
        sys.exit(EXIT_PRECONDITION_FAILED)
    elif "READY" in sim_status:
        log("SIM is ready.")
    else:
        log("Unknown SIM status.")
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

    # Step 4: 5G Registration
    reg_output = run_at_command("AT+C5GREG?")
    reg_status = parse_c5greg(reg_output)
    if reg_status in [1, 5]:
        log(f"Registered to 5G ({'Home' if reg_status == 1 else 'Roaming'})")
    else:
        log(f"Not registered to 5G. C5GREG: {reg_status}")
        sys.exit(EXIT_PRECONDITION_FAILED)

    # Step 5: Check PCI lock
    lock_output = run_at_command("AT#5GBCCHLOCK?")
    pci_lock_status = get_pci_lock_status(lock_output)
    log(f"PCI Lock is currently: {pci_lock_status}")
    if pci_lock_status == "ENABLED":
        log("PCI Lock is ENABLED. Exiting.")
        sys.exit(EXIT_PRECONDITION_FAILED)

    # Step 6: Get current NR cell
    nrds_output = run_at_command("AT#NRDS")
    current = parse_nrds(nrds_output)
    if not current:
        log("Failed to parse NRDS.")
        sys.exit(EXIT_CMDS_NON_RESPONSIVE)
    log(f"Current NR Cell: BAND={current['band']}, ARFCN={current['arfcn']}, PCI={current['pci']}, SCS={current['scs']}")

    # Step 7: Scan neighbors
    retries = 3
    neighbors = []
    for i in range(retries):
        log(f"Scanning 5G neighbors (attempt {i+1})...")
        csurv_output = run_at_command("AT#CSURV")
        neighbors = parse_csurv_neighbors(csurv_output)
        if neighbors:
            break
        time.sleep(20)

    if not neighbors:
        log("No neighbors found after retries.")
        sys.exit(EXIT_CMDS_NON_RESPONSIVE)

    # Step 8: Select neighbor
    chosen = next((n for n in neighbors if n["arfcn"] != current["arfcn"] or n["pci"] != current["pci"]), None)
    if not chosen:
        log("No different neighbor found.")
        sys.exit(EXIT_CMDS_NON_RESPONSIVE)

    log(f"Locking to Neighbor: BAND={chosen['band']}, ARFCN={chosen['arfcn']}, PCI={chosen['pci']}, SCS={chosen['scs']}")

    # Step 9: Apply lock
    lock_cmd = f"AT#5GBCCHLOCK=0,{chosen['scs']},{chosen['arfcn']},{chosen['pci']},{chosen['band']}"
    run_at_command(lock_cmd)

    # Step 10: Reboot
    run_at_command("AT#ENHRST=1,0")
    log("Rebooting device... Waiting 90 seconds.")
    time.sleep(90)

    # Step 11: Verify lock
    nrds_after = run_at_command("AT#NRDS")
    locked = parse_nrds(nrds_after)
    if locked and locked["arfcn"] == chosen["arfcn"] and locked["pci"] == chosen["pci"]:
        log("PCI Lock SUCCESSFUL after reboot.")
        log(f"Locked to BAND={locked['band']}, ARFCN={locked['arfcn']}, PCI={locked['pci']}, SCS={locked['scs']}")
        log("TEST PASSED!!!!!")
        sys.exit(EXIT_SUCCESS)
    else:
        log("PCI Lock FAILED after reboot.")
        if locked:
            log(f"Now on BAND={locked['band']}, ARFCN={locked['arfcn']}, PCI={locked['pci']}, SCS={locked['scs']}")
        log("TEST FAILED!!!!!")
        sys.exit(EXIT_FAILED)

    log("5G PCI LOCK TEST COMPLETE.")

if __name__ == "__main__":
    main()

