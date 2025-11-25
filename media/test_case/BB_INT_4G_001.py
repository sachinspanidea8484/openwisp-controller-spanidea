import re
import sys
import time
import subprocess
from datetime import datetime

# === CONFIGURATION ===
BB_QMI_DEVICE = "/dev/cdc-wdm0"
BB_APN = "fast.t-mobile.com"
REMOTE_PING_IP = "8.8.8.8"  # Google for ping tests
LOG_FILE = "BB_INT_4G_001.log"

# === EXIT CODES ===
EXIT_SUCCESS = 0
EXIT_FAILED = 1
EXIT_PRECONDITION_FAILED = 2
EXIT_CMDS_NON_RESPONSIVE = 3

# Global max retries
MAX_RETRIES = 3


# === TEST DURATIONS ===
TEST_DURATION = 60  # 1 minutes for stability

# === LOGGING ===
def timestamp():
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

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

# === HELPER FUNCTIONS ===
def find_modem_interface():
    log("Fetching modem IPv4 from uqmi...")
    settings_out, _ = run_cmd(f"uqmi -d {BB_QMI_DEVICE} --get-current-settings")
    ip_match = re.search(r'"ip":\s*"(\d+\.\d+\.\d+\.\d+)"', settings_out)
    if not ip_match:
        log("Could not parse IPv4 from uqmi output.")
        return None, None
    modem_ip = ip_match.group(1)
    log(f"Detected modem IP: {modem_ip}")

    ifconfig_out, _ = run_cmd("ifconfig wwan0")
    iface_name = None
    current_iface = None

    for line in ifconfig_out.splitlines():
        match_iface = re.match(r"^(\S+)\s+Link", line)
        if match_iface:
            current_iface = match_iface.group(1)
            continue
        if modem_ip in line:
            iface_name = current_iface
            break

    if iface_name:
        log(f"Found interface: {iface_name}")
        return iface_name, modem_ip

    # Fallback to `ip addr` if needed
    ip_addr_out, _ = run_cmd("ip -4 addr show")
    for block in ip_addr_out.split("\n\n"):
        match_iface = re.match(r"\d+: (\S+):", block)
        if match_iface:
            iface = match_iface.group(1)
            if modem_ip in block:
                log(f"Found interface: {iface}")
                return iface, modem_ip

    log("Still could not find interface for modem IP.")
    return None, modem_ip

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
    


def check_signal_info():
    log("Checking signal info...")
    signal_info, _ = run_cmd(f"uqmi -d {BB_QMI_DEVICE} --get-signal-info")
    if "nr5g" in signal_info.lower():
        log(f"Connected to 5G: {signal_info}")
        return "5G"
    elif "lte" in signal_info.lower():
        log(f"Connected to 4G: {signal_info}")
        return "4G"
    else:
        log(f"Unknown network type: {signal_info}")
        return None

def ping_remote(iface):
    log(f"Pinging {REMOTE_PING_IP} via {iface}...")
    output, _ = run_cmd(f"ping -I {iface} -c 4 {REMOTE_PING_IP}")
    if "100% packet loss" in output or "0 received" in output:
        log("Ping failed.")
        return False
    log("Ping successful.")
    return True

   
# === MAIN LOGIC ===
def main():
    log("Starting 4G WAN Interface Test BB-INT-4G-001...")

    try:
        if ensure_modem_connected():
            log("Modem connection established successfully.")
        else:
            log("TEST FAILED!!!:- Modem failed to connect after max retries")
            sys.exit(EXIT_PRECONDITION_FAILED)

        iface, modem_ip = find_modem_interface()
        if not iface:
            log("TEST FAILED !!!!! - No interface found. Aborting.")
            sys.exit(EXIT_PRECONDITION_FAILED)

        network_type = check_signal_info()
        if not network_type:
            log("TEST FAILED !!!!! - Could not determine network type. Aborting.")
            sys.exit(EXIT_CMDS_NON_RESPONSIVE)

        if not ping_remote(iface):
            log("TEST FAILED !!!!! - Connectivity check failed.")
            sys.exit(EXIT_FAILED)

        log(f"Initial connectivity check PASSED: {network_type} via {iface} ({modem_ip}).")

        # === Verify session stability for {TEST_DURATION} ===
        log(f"Starting {TEST_DURATION} seconds session stability verification...")
        start = time.time()
        while time.time() - start < TEST_DURATION:
            if not ping_remote(iface):
                log("TEST FAILED !!!!! - Ping failed during stability test.")
                sys.exit(EXIT_FAILED)
            time.sleep(30)

        log(f"TEST PASSED !!!!! - Stability test completed successfully for {TEST_DURATION} seconds.")
        sys.exit(EXIT_SUCCESS)

    except Exception as e:
        log(f"TEST FAILED !!!!! - Exception: {e}")
        sys.exit(EXIT_FAILED)

if __name__ == "__main__":
    main()

