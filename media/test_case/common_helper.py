"""
Common Helper for NBAPI Testcases
"""
import os
import sys
import json
import subprocess
from datetime import datetime

EXIT_SUCCESS = 0
EXIT_FAILED = 1

def log(message, *args, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if args:
        try:
            message = message % args
        except Exception:
            message = f"{message} {args}"
    print(f"{timestamp} [{level}] {message}")

def run_local_command(command, check=True, capture_output=True, text=True, shell=True, allow_fail=False):
    log("Executing command: %s", command)
    try:
        result = subprocess.run(command, shell=shell, capture_output=capture_output, text=text, check=check)
        return (result.stdout.strip() if result.stdout else "",
                result.stderr.strip() if result.stderr else "",
                result.returncode)
    except subprocess.CalledProcessError as e:
        if not allow_fail:
            log("Command failed (RC=%d): %s", e.returncode, command, level="FAIL")
            raise
        return ("", e.stderr.strip() if e.stderr else "", e.returncode)

def verify_file_exists(filepath):
    if not os.path.isfile(filepath):
        log("File not found: %s", filepath, level="FAIL")
        return False
    log("Verified file exists: %s", filepath, level="PASS")
    return True

def parse_configuration(config_str):
    if not config_str:
        log("Empty CONFIGURATION argument", level="FAIL")
        sys.exit(EXIT_FAILED)
    if config_str.startswith("CONFIGURATION"):
        config_str = config_str.split("=", 1)[-1]
    try:
        return json.loads(config_str)
    except json.JSONDecodeError as e:
        log("Invalid CONFIGURATION JSON: %s", e, level="FAIL")
        sys.exit(EXIT_FAILED)

def get_up_interfaces():
    stdout, _, _ = run_local_command("ip -o addr show | grep -v lo | awk '{print $2}' | sort -u", allow_fail=True)
    return stdout.split() if stdout else []

def update_rc_local(script_path, config_str):
    exec_line = f"python3 {script_path} 'REBOOT_CONTEXT CONFIGURATION={config_str}'"
    if not os.path.exists("/etc/rc.local"):
        with open("/etc/rc.local", "w") as f:
            f.write("#!/bin/sh -e\n\nexit 0\n")
    with open("/etc/rc.local", "r") as f:
        lines = f.readlines()
    if any(script_path in line for line in lines):
        log("rc.local already contains entry for %s", script_path)
        return
    with open("/etc/rc.local", "w") as f:
        for line in lines:
            if line.strip() == "exit 0":
                f.write(f"{exec_line}\n")
            f.write(line)
    log("Added reboot hook to rc.local for %s", script_path, level="PASS")

def clear_rc_local(script_path):
    if not os.path.exists("/etc/rc.local"):
        return
    with open("/etc/rc.local", "r") as f:
        lines = f.readlines()
    with open("/etc/rc.local", "w") as f:
        for line in lines:
            if script_path not in line:
                f.write(line)
    log("Removed rc.local entry for %s", script_path, level="PASS")

def extract_target_block(output, target_sensor):
    lines = output.splitlines()
    block = []
    inside_target = False
    for line in lines:
        if target_sensor in line:
            inside_target = True
            block.append(line)
            continue
        if inside_target:
            if line.strip() == "":
                break
            block.append(line)
    return "\n".join(block)

def parse_sensor_output(block):
    voltage = None
    current = None
    for line in block.splitlines():
        if "Bus Voltage" in line:
            try:
                voltage = float(line.split(":")[1].strip())
            except Exception:
                pass
        elif "Current (A)" in line:
            try:
                current = float(line.split(":")[1].strip())
            except Exception:
                pass
    return voltage, current



######################################################################

def parse_ip_stats(output):
    stats = {
        "rx_packets": 0,
        "rx_errors": 0,
        "rx_dropped": 0,
        "tx_packets": 0,
        "tx_errors": 0,
        "tx_dropped": 0,
    }

    lines = output.splitlines()

    for i, line in enumerate(lines):
        line = line.strip()

        try:
            if line.startswith("RX:") and i + 1 < len(lines):
                vals = lines[i + 1].split()
                stats["rx_packets"] = int(vals[1])
                stats["rx_errors"] = int(vals[2])
                stats["rx_dropped"] = int(vals[3])

            if line.startswith("TX:") and i + 1 < len(lines):
                vals = lines[i + 1].split()
                stats["tx_packets"] = int(vals[1])
                stats["tx_errors"] = int(vals[2])
                stats["tx_dropped"] = int(vals[3])
        except (IndexError, ValueError):
            continue

    return stats


def validate_ifconfig_errors(interface, threshold_percent=10):
    """
    Validate RX/TX error percentage on given interface.
    :param interface: Interface name (e.g., wwan0)
    :param threshold_percent: Allowed error percentage
    """

    log("=== IFCONFIG ERROR VALIDATION START ===")
    log("Interface: %s | Threshold: %.3f%%", interface, threshold_percent)

    stdout, stderr, rc = run_local_command(
        f"ip -s link show {interface}",
        allow_fail=True
    )

    if rc != 0:
        log("TEST FAILED: Unable to get interface stats (%s)", stderr, level="ERROR")
        return False

    stats = parse_ip_stats(stdout)

    rx_pkts = max(stats["rx_packets"], 1)
    tx_pkts = max(stats["tx_packets"], 1)

    rx_err = stats["rx_errors"] + stats["rx_dropped"]
    tx_err = stats["tx_errors"] + stats["tx_dropped"]

    rx_pct = (rx_err / rx_pkts) * 100
    tx_pct = (tx_err / tx_pkts) * 100

    log("RX Packets=%d | Errors+Dropped=%d | Error%%=%.3f%%",
        rx_pkts, rx_err, rx_pct)

    log("TX Packets=%d | Errors+Dropped=%d | Error%%=%.3f%%",
        tx_pkts, tx_err, tx_pct)

    if rx_pct > threshold_percent or tx_pct > threshold_percent:
        log("=== TEST FAILED: Error threshold exceeded ===", level="ERROR")
        return False

    log("=== TEST PASSED: Error threshold within limits ===")
    return True

def parse_config(config_str):
   
    if config_str.startswith("CONFIGURATION="):
        config_str = config_str[len("CONFIGURATION="):]
 
    try:
        return json.loads(config_str)
    except json.JSONDecodeError as e:
        print(f"Error parsing CONFIGURATION JSON: {e}", file=sys.stderr)
        return {}
    

def get_modem_status(interface):
    log(f"Getting modem full status for {interface}...")

    # Modem sections
    stdout, _, rc = run_local_command("uci show network | grep '.device='", allow_fail=True)

    if rc != 0 or not stdout.strip():
        log("No modem entries found in UCI", level="FAIL")
        return None

    modem_sections = set()
    for line in stdout.splitlines():
        try:
            section = line.split('.')[1]
            modem_sections.add(section)
        except Exception:
            continue

    modem_name = None
    qmi_device = None

    # interface -> modem
    for modem in modem_sections:
        stdout, _, rc = run_local_command(f"ifstatus {modem}", allow_fail=True)
        if rc != 0 or not stdout:
            continue

        try:
            status_json = json.loads(stdout)
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

    qmi_base = os.path.basename(qmi_device)
    stdout, _, rc = run_local_command(f"readlink -f /sys/class/usbmisc/{qmi_base}/device/..", allow_fail=True)

    if rc != 0 or not stdout.strip():
        log("Failed to determine USB parent path", level="FAIL")
        return None

    usb_device_root = stdout.strip()

    stdout, _, rc = run_local_command(f"find {usb_device_root} -maxdepth 2 -name 'ttyUSB*'", allow_fail=True)
    
    at_port = None
    if rc == 0 and stdout:
        unique_ports = {f"/dev/{os.path.basename(p.strip())}" for p in stdout.splitlines() if 'ttyUSB' in p}
        potential_ports = sorted(list(unique_ports))
        
        for tty_dev in potential_ports:
            probe_cmd = f"echo 'AT' | socat -T 1 - '{tty_dev},raw,echo=0,crnl'"
            resp, _, _ = run_local_command(probe_cmd, allow_fail=True)

            if resp and "OK" in resp:
                at_port = tty_dev
                break

    if not at_port:
        log("No functional AT port detected", level="WARN")

    # Detect Network Type 
    stdout, _, rc = run_local_command(f"qmicli -d {qmi_device} --nas-get-signal-info", allow_fail=True)
    
    network_type = "No Signal"
    if rc == 0 and stdout:
      
        has_5g = re.search(r"5G:.*?RSRP:\s+'-\d+", stdout, re.DOTALL | re.IGNORECASE)
        has_lte = re.search(r"LTE:.*?RSRP:\s+'-\d+", stdout, re.DOTALL | re.IGNORECASE)

        if has_5g:
            network_type = "5G"
        elif has_lte:
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
   
