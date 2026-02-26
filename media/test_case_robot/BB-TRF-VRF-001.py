# START_DESCRIPTION

#1.Connect to DUT, CE1, CE2, and PE2 using SSH.
#2.Create the VRF on DUT and assign the interface and IP address to it.
#3.Create the VRF on PE2 and assign the interface and IP address to it.
#4.Check that the VRF is successfully created on DUT.
#5.Check that the VRF is successfully created on PE2.
#6.Ping from CE1 to CE2 to verify connectivity.
#7.Ping from CE2 to CE1 to verify reverse connectivity.
#8.Pass the test if VRF creation and both ping tests are successful.

# END_DESCRIPTION

import os
from datetime import datetime
from robot.api.deco import keyword
from robot.libraries.BuiltIn import BuiltIn
from execution.executor_helper import get_registered_executor

# ================= LOGGING =================
LOG_FOLDER = os.path.join(os.path.dirname(__file__), '..', '..', 'logs')
os.makedirs(LOG_FOLDER, exist_ok=True)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE_PATH = os.path.join(LOG_FOLDER, f"vrf_log_{timestamp}.log")

def log(message: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    BuiltIn().log_to_console(f"[{ts}] {message}")
    with open(LOG_FILE_PATH, "a") as f:
        f.write(f"[{ts}] {message}\n")

def get_executor(device_name):
    executor = get_registered_executor(device_name)
    if not executor:
        raise RuntimeError(f"No executor registered for device '{device_name}'")
    return executor

def run_cmd(device_name, executor, cmd):
    log(f"[{device_name}] $ {cmd}")
    result = executor.execute(cmd)
    stdout = getattr(result, "stdout", "").strip()
    stderr = getattr(result, "stderr", "").strip()
    if stdout:
        log(f"[{device_name}] STDOUT:\n{stdout}")
    if stderr:
        log(f"[{device_name}] STDERR:\n{stderr}")
    return result

def detect_os(device_name):
    executor = get_executor(device_name)
    result = run_cmd(device_name, executor, "cat /etc/os-release 2>/dev/null || true")
    os_info = (getattr(result, "stdout", "")).lower()
    return "openwrt" if "openwrt" in os_info else "linux"

# ================= CREATE VRF =================
@keyword("CREATE VRF")
def create_vrf(device_name, vrf_name, table_id, interface, vrf_ip):
    log(f"[{device_name}] Creating VRF: {vrf_name}")
    executor = get_executor(device_name)
    os_type = detect_os(device_name)

    sudo_prefix = "" if os_type == "openwrt" else "sudo "

    commands = [
        f"{sudo_prefix}ip link add {vrf_name} type vrf table {table_id} || true",
        f"{sudo_prefix}ip link set dev {vrf_name} up",
        f"{sudo_prefix}ip link set dev {interface} master {vrf_name} || true",
        f"{sudo_prefix}ip addr flush dev {interface}",
        f"{sudo_prefix}ip addr add {vrf_ip} dev {interface}",
        f"{sudo_prefix}ip link set dev {interface} up",
    ]

    for cmd in commands:
        run_cmd(device_name, executor, cmd)

    log(f"[{device_name}] VRF '{vrf_name}' configured successfully")

# ================= CHECK VRF =================
@keyword("CHECK LINUX VRF")
def check_linux_vrf(device_name, vrf_name):
    log(f"[{device_name}] Checking VRF existence: {vrf_name}")
    executor = get_executor(device_name)
    result = run_cmd(device_name, executor, "ip link show type vrf")
    output = getattr(result, "stdout", "")
    exists = vrf_name in output
    log(f"[{device_name}] VRF exists = {exists}")
    return exists

# ================= PING =================
@keyword("PING TEST")
def ping_test(device_name, target):
    log(f"[{device_name}] Pinging {target}")
    executor = get_executor(device_name)
    result = run_cmd(device_name, executor, f"ping -c 4 {target}")
    output = getattr(result, "stdout", "")
    success = "0% packet loss" in output
    log(f"[{device_name}] Ping success = {success}")
    return success

