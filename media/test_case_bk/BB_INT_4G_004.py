import re
import sys
import time
import subprocess
from datetime import datetime

# === CONFIGURATION ===
BB_AT_PORT = "/dev/ttyUSB3"
BB_QMI_DEVICE = "/dev/cdc-wdm0"
LOG_FILE = "BB_INT_4G_004.log"

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
        return {
            "earfcn": earfcn,
            "pci": pci,
            "lock_enabled": lock_enabled
        }
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
        status_out = status_out.strip().strip('"')  # clean quotes/spaces

        if status_out.lower() == "connected":
            log("Modem is connected.")
            return True

        log(f"Attempt {attempt}/{MAX_RETRIES}: Modem disconnected ({status_out}), retrying...")
        run_cmd("ifup Modem1 && ifup Modem2")
        time.sleep(30)

    # After retries, still disconnected
    log("Modem failed to connect after max retries.")
    return False

# === Main Script ===
def main():
    log("===Starting 4G PCI UNLOCK Test BB-INT-4G-004===")
    
    try:
        # Keep trying until modem connects

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
        if ensure_modem_connected():
            log("Modem connection established successfully.")
        else:
            log("TEST FAILED!!!:- Modem failed to connect after max retries")
            sys.exit(EXIT_PRECONDITION_FAILED) 

        # Step 3: Check if PCI lock is enabled
        log("===Checking current PCI lock====")
        bcchlock_out, _ = at_cmd("AT#BCCHLOCK?")
        bcch_status = parse_bcchlock(bcchlock_out)
        if bcch_status:
            if bcch_status["lock_enabled"]:
                log(f"PCI Lock ENABLED: EARFCN={bcch_status['earfcn']}, "
                    f"PCI={bcch_status['pci']} (0x{bcch_status['pci']:X})")
                log("Sending command to DISABLE PCI lock...")
                at_cmd("AT#BCCHLOCK=1024,0,65535,0,0")
            else:
                log("TEST FAILED!!! :- PCI Lock is already DISABLED.")
                sys.exit(EXIT_PRECONDITION_FAILED)
        else:
            log("TEST FAILED!!! :- Could not parse BCCHLOCK status.")
            sys.exit(EXIT_PRECONDITION_FAILED)

        # Step 4: Confirm PCI lock is disabled
        log("===Checking PCI lock status====")
        bcchlock_output, _ = at_cmd("AT#BCCHLOCK?")
        bcch_status = parse_bcchlock(bcchlock_output)

        if bcch_status and bcch_status["earfcn"] == 0 and bcch_status["pci"] == 0:
            log("PCI Lock is successfully DISABLED.")
            log("TEST PASSED!!!!!")
            sys.exit(EXIT_SUCCESS)
        else:
            log(f"PCI Lock still ENABLED: EARFCN={bcch_status['earfcn']}, "
                f"PCI={bcch_status['pci']} (0x{bcch_status['pci']:X})")
            log("TEST FAILED!!!!")
            sys.exit(EXIT_FAILED)

            
        log("4G PCI UNLOCK TEST COMPLETE.")
    except Exception as e:
        log(f"TEST FAILED !!!!! - Exception: {e}")
        sys.exit(EXIT_FAILED)

if __name__ == "__main__":
    main()

