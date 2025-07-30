import subprocess
import time
import sys  # Add this import for exit codes
from datetime import datetime

# === CONFIGURATION ===
BB_AT_PORT = "/dev/ttyUSB3"
REMOTE_PC_IP = "192.168.1.100"  # Set your remote PC IP here
TEST_DURATION = 10
OUTPUT_FILE = "output_iperf_test_at.txt"
LOG_FILE = "BB_INT_5G_001.log"

# === EXIT CODES ===
EXIT_SUCCESS = 0
EXIT_MODEM_NOT_RESPONDING = 1
EXIT_SIM_NOT_INSERTED = 2
EXIT_SIM_PIN_REQUIRED = 3
EXIT_SIM_UNKNOWN_STATE = 4
EXIT_NOT_REGISTERED_5G = 5
EXIT_NO_IP_ADDRESS = 6
EXIT_REMOTE_PC_UNREACHABLE = 7
EXIT_IPERF_FAILED = 8

# === LOGGING ===
def timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log(message):
    line = f"[+] {timestamp()} - {message}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def log_error(message, exit_code):
    """Log error message and exit with specified code"""
    line = f"[ERROR] {timestamp()} - {message} (Exit code: {exit_code})"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")
    sys.exit(exit_code)

def run_at_cmd(command):
    full_cmd = f"echo -e '{command}\\r' | socat - {BB_AT_PORT},raw,echo=0,crnl"
    try:
        result = subprocess.check_output(full_cmd, shell=True, stderr=subprocess.STDOUT)
        return result.decode().strip()
    except subprocess.CalledProcessError as e:
        return e.output.decode().strip()

def is_ip_reachable(ip):
    log(f"Pinging remote PC at {ip}...")
    result = subprocess.run(["ping", "-c", "1", "-W", "1", ip],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    return result.returncode == 0

# === MAIN LOGIC ===
def main():
    log("Starting 5G WAN test with AT prechecks...")
    log("Verifying modem responsiveness...")

    modem_ok = run_at_cmd("AT")
    if "OK" not in modem_ok:
        log_error("Modem not responding. Aborting.", EXIT_MODEM_NOT_RESPONDING)

    log("Enabling CME ERRORs for better AT feedback...")
    run_at_cmd("AT+CMEE=1")

    log("Running AT commands...")
    cmee_status = run_at_cmd("AT+CMEE?")
    log(f"CME Status: {cmee_status}")

    sim_status = run_at_cmd("AT+CPIN?")
    log(f"SIM Status: {sim_status}")

    if "+CME ERROR: 10" in sim_status:
        log_error("SIM not inserted. Please insert the SIM card. Test aborted.", EXIT_SIM_NOT_INSERTED)
    elif "+CPIN: SIM PIN" in sim_status:
        log_error("SIM is inserted but waiting for PIN entry. Test aborted.", EXIT_SIM_PIN_REQUIRED)
    elif "READY" in sim_status:
        log("SIM is ready. Proceeding...")
    else:
        log_error(f"Unknown SIM state: {sim_status}. Test aborted.", EXIT_SIM_UNKNOWN_STATE)

    imsi = run_at_cmd("AT+CIMI")
    log(f"IMSI: {imsi}")

    reg_status = run_at_cmd("AT+C5GREG?")
    log(f"5G Registration: {reg_status}")

    if "+C5GREG: 1,1" not in reg_status:
        log_error("Not registered on 5G. Test aborted.", EXIT_NOT_REGISTERED_5G)

    ip_addr = run_at_cmd("AT+CGPADDR=1")
    log(f"IP Address Assigned: {ip_addr}")

    if "+CGPADDR" not in ip_addr:
        log_error("No PDP IP address assigned. Test aborted.", EXIT_NO_IP_ADDRESS)

    pdp_status = run_at_cmd("AT+CGACT?")
    band_status = run_at_cmd("AT#BND?")
    serving_cell = run_at_cmd("AT#SERVINFO")

    log(f"PDP Context Active: {pdp_status}")
    log(f"Band Config: {band_status}")
    log(f"Serving Cell Info: {serving_cell}")

    log("All preconditions met. Starting iperf3 test...")

    if not is_ip_reachable(REMOTE_PC_IP):
        log_error(f"Remote PC {REMOTE_PC_IP} not reachable. Test aborted.", EXIT_REMOTE_PC_UNREACHABLE)

    log(f"Running iperf3 client to remote PC: {REMOTE_PC_IP}")
    with open(OUTPUT_FILE, "w") as outfile:
        result = subprocess.run(["iperf3", "-c", REMOTE_PC_IP, "-t", str(TEST_DURATION)],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        output = result.stdout.decode()
        outfile.write(output)
        with open(LOG_FILE, "a") as logf:
            logf.write(output)

    if result.returncode != 0:
        log_error("iperf3 client failed.", EXIT_IPERF_FAILED)

    log(f"Test completed successfully. Log saved to {LOG_FILE}")
    sys.exit(EXIT_SUCCESS)

if __name__ == "__main__":
    main()

