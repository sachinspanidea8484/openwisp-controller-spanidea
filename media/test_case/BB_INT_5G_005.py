import subprocess
import re
import time
from datetime import datetime
import sys

# === CONFIGURATION ===
BB_AT_PORT = "/dev/ttyUSB3"
LOG_FILE = "BB_INT_5G_005_UNLOCK.log"

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
        result = subprocess.run(
            ["sh", "-c", f"echo -e '{cmd}\\r' | socat - {BB_AT_PORT},raw,echo=0,crnl"],
            capture_output=True,
            text=True,
            timeout=10
        )
        output = result.stdout.strip()
        log(f"[OUT] {output}")
        time.sleep(1)
        return output
    except Exception as e:
        log(f"[ERROR] Failed to run command: {cmd} -- {e}")
        return ""

# === PARSERS ===
def parse_c5greg(output):
    match = re.search(r"\+C5GREG:\s*\d+,(\d+)", output)
    return int(match.group(1)) if match else None

def parse_nrds(output):
    match = re.search(
        r"#NRDS:\s*(\d+)/[^,]*,[^,]*,(\d+),(\d+),.*?,.*?,.*?,.*?,.*?,.*?,.*?/.*?,.*?/.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,(\d+)",
        output
    )
    if match:
        return {
            "band": int(match.group(1)),
            "arfcn": int(match.group(2)),
            "pci": int(match.group(3)),
            "scs": int(match.group(4))
        }
    return None

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
    log("Starting 5G PCI Unlock Test...")
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

    # Step 2: Check PDP context
    pdp_output = run_at_command("AT+CGDCONT?")
    log("PDP Context (APN) Info:")
    log(pdp_output if pdp_output else " No PDP Context found.")

    # Step 3: Check packet domain attach
    cgatt_output = run_at_command("AT+CGATT?")
    if "+CGATT: 1" in cgatt_output:
        log("Device is attached to the packet domain.")
    else:
        log("Device is NOT attached to the packet domain.")
        #sys.exit(EXIT_PRECONDITION_FAILED)

    # Step 4: 5G Registration
    reg_output = run_at_command("AT+C5GREG?")
    reg_status = parse_c5greg(reg_output)
    if reg_status in [1, 5]:
        log(f"Registered to 5G network ({'Home' if reg_status == 1 else 'Roaming'})")
    else:
        log(f"Not registered to 5G. C5GREG: {reg_status}")
        #sys.exit(EXIT_PRECONDITION_FAILED)

    # Step 5: Check PCI Lock
    lock_output = run_at_command("AT#5GBCCHLOCK?")
    pci_lock_status = get_pci_lock_status(lock_output)
    log(f"PCI Lock is currently: {pci_lock_status}")
    
    if pci_lock_status == "ENABLED":
        log("PCI Lock is ENABLED. Continuing with UNLOCKING steps...")
        run_at_command("AT#5GBCCHLOCK=2") 
    else:
        log("PRECONDITION FAILED: PCI Lock is DISABLED. Exiting...")
        sys.exit(EXIT_PRECONDITION_FAILED)
        
    # Step 6: Reboot
    run_at_command("AT#ENHRST=1,0")
    log("Rebooting... waiting 90s")
    time.sleep(90)

    # Step 7: Read current NR cell
    nrds_output = run_at_command("AT#NRDS")
    current = parse_nrds(nrds_output)

    # Step 8: Re-check PCI lock
    lock_output = run_at_command("AT#5GBCCHLOCK?")
    pci_lock_status = get_pci_lock_status(lock_output)
    log(f"PCI Lock is currently: {pci_lock_status}")

    if pci_lock_status == "ENABLED":
        log("PCI Lock is ENABLED. TEST FAILED!!!!!")
        sys.exit(EXIT_FAILED)  
    else:
        log("PCI Lock is DISABLED. TEST PASSED!!!!!")
        sys.exit(EXIT_SUCCESS)

    log("5G PCI UNLOCK TEST COMPLETE!!!!!!.")

if __name__ == "__main__":
    main()

