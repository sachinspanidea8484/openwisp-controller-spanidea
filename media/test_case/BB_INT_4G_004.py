import re
import sys
import time
import subprocess
from datetime import datetime

# === CONFIGURATION ===
BB_AT_PORT = "/dev/ttyUSB3"
LOG_FILE = "BB_INT_4G_004_UNLOCK.log"

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

# === PARSERS ===
def parse_cereg(output):
    match = re.search(r"\+CEREG:\s*\d+,(\d+)", output)
    return int(match.group(1)) if match else None

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

# === MAIN SCRIPT ===
def main():
    log("Starting 4G PCI Unlock Test...")
    # Step 1: Check SIM status
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
   
    # Step 2: Packet domain attach
    cgatt_output = run_at_command("AT+CGATT?")
    if "+CGATT: 1" in cgatt_output:
        log("Attached to packet domain.")
    else:
        log("Not attached to packet domain.")
        #sys.exit(EXIT_PRECONDITION_FAILED)

    # Step 3: Check 4G Registration
    nw_status_output = run_at_command("AT+CEREG?")
    reg_status = parse_cereg(nw_status_output)
    if reg_status in [1, 5]:
        log(f"Registered to 4G network ({'Home' if reg_status == 1 else 'Roaming'})")
    else:
        log(f"Not registered to 4G network. CEREG status: {reg_status}")
        #sys.exit(EXIT_PRECONDITION_FAILED)
    
     # Step 4: PDP context
    pdp_output = run_at_command("AT+CGCONTRDP")
    log("PDP Context Info:")
    log(pdp_output or " No PDP context configured.")

    # Step 5: Check if PCI lock is enabled
    log("Checking current PCI lock...")
    bcchlock_output = run_at_command("AT#BCCHLOCK?")
    bcch_status = parse_bcchlock(bcchlock_output)

    if bcch_status:
        if bcch_status["lock_enabled"]:
            log(f"PCI Lock is ENABLED: EARFCN={bcch_status['earfcn']}, PCI={bcch_status['pci']} (0x{bcch_status['pci']:X})")
            log("Sending command to DISABLE PCI lock...")
            run_at_command("AT#BCCHLOCK=1024,0,65535,0,0")
        else:
            log("PCI Lock is already DISABLED.")
            sys.exit(EXIT_PRECONDITION_FAILED)
    else:
        log("Could not parse BCCHLOCK status. Proceeding to unlock...")
        sys.exit(EXIT_CMDS_NON_RESPONSIVE)

  
    # Step 6: Confirm PCI lock is disabled
    log("Checking PCI lock status....")
    bcchlock_output = run_at_command("AT#BCCHLOCK?")
    bcch_status = parse_bcchlock(bcchlock_output)

   
    if bcch_status["earfcn"] == 0 and bcch_status["pci"] == 0:
          log("PCI Lock is successfully DISABLED.")
          log("TEST PASSED!!!!!")
          sys.exit(EXIT_SUCCESS)
    else:
          log(f"PCI Lock still ENABLED: EARFCN={bcch_status['earfcn']}, PCI={bcch_status['pci']} (0x{bcch_status['pci']:X})")
          log("TEST FAILED!!!!")
          sys.exit(EXIT_FAILED)
          
    log("4G PCI UNLOCK TEST COMPLETE.")

if __name__ == "__main__":
    main()
