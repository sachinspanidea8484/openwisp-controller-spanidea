# START_DESCRIPTION 
#1. Initialize logging and establish connections to DUT & to RPi.
#2. Check the DUT connection, signal information and default route.
#3. Configure Wi-Fi AP on DUT.
#4. Configure RPi and Connect to Wi-Fi AP.
#5. Baseline connectivity check via ping & collect the latency.
#6. Print baseline stats on DUT (CPU, memory used, interrupts).
#7. Check RPi routing and connectivity
#8. Keep printing baseline stats on DUT while test is running (CPU, memory used, interrupts)
#9. Collect logs/results
#10. Print baseline stats on DUT after test completion (CPU, memory used, interrupts).
# END_DESCRIPTION


import os
import re
import json
import time
import threading
from datetime import datetime
from robot.api.deco import keyword
from robot.libraries.BuiltIn import BuiltIn
from execution.executor_helper import get_registered_executor
 
from execution.common_helper import ( monitor_system_stats_around_iperf, 
                                     wait_for_monitoring_to_finish,
                                     capture_ifconfig_snapshot_for_devices,
                                     validate_ifconfig_errors_for_devices,)
# ============================================================
# LOGGING (COMMON FORMAT)
# ============================================================
LOG_FOLDER = os.path.join(os.path.dirname(__file__), "..", "..", "logs")
os.makedirs(LOG_FOLDER, exist_ok=True)

LOG_FILE_PATH = os.path.join(
    LOG_FOLDER,
    f"custom_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
)


def log_message(message: str):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    BuiltIn().log_to_console(line)
    with open(LOG_FILE_PATH, "a") as f:
        f.write(line + "\n")


@keyword("Initialize Custom Log File")
def initialize_custom_log_file():
    log_message("[STEP] Custom log initialized")


@keyword("Log Message To Custom File")
def log_message_to_custom_file(message: str):
    log_message(message)


MAX_RETRIES = 3
# ============================================================
# MODEM / WWAN
# ============================================================

def get_qmi_and_modem_from_interface_remote(executor, interface):

    result = executor.execute("uci show network | grep '.device='")

    if not result.stdout.strip():
        raise AssertionError("No modem device entries found in UCI")

    modem_sections = []

    for line in result.stdout.splitlines():
        # network.Modem1.device='/dev/cdc-wdm0'
        section = line.split(".")[1]
        modem_name = section.split(".")[0]
        modem_sections.append(modem_name)

    for modem in modem_sections:

        status_result = executor.execute(f"ifstatus {modem}")
        try:
            status_json = json.loads(status_result.stdout)
        except:
            continue

        if status_json.get("l3_device") == interface:
            device_result = executor.execute( f"uci get network.{modem}.device")
            qmi_device = device_result.stdout.strip()

            return qmi_device, modem

    raise AssertionError(f"No modem mapped to interface {interface}")



@keyword("Ensure Modem Connected")
def Ensure_Modem_Connected(device_name, interface):

    executor = get_registered_executor(device_name)

    qmi_device, modem_device = get_qmi_and_modem_from_interface_remote(executor, interface)
    
    log_message(f"[MODEM] Interface {interface}")
    log_message(f"[MODEM] QMI Device: {qmi_device}")
    log_message(f"[MODEM] Modem Section: {modem_device}")


    log_message(f"Checking modem connection for {interface}...")

    # Step 1: Ensure Modem Connected
    for attempt in range(1, MAX_RETRIES + 1):

        result = executor.execute(f"uqmi -d {qmi_device} --get-data-status")

        if result.failed:
            raise AssertionError(
                f"Failed to check modem data status on {device_name}\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )

        status = result.stdout.strip().strip('"').lower()

        if status == "connected":
            log_message("Modem is connected.")
            break

        log_message(f"Attempt {attempt}/{MAX_RETRIES}: Modem disconnected, retrying...")

        retry_result = executor.execute(f"ifup {modem_device}")

        if retry_result.failed:
            raise AssertionError(
                f"ifup failed for {modem_device} on {device_name}\n"
                f"stdout: {retry_result.stdout}\n"
                f"stderr: {retry_result.stderr}"
            )

        time.sleep(60)

    else:
        raise AssertionError("Modem failed to connect after max retries")

    # Step 2: Detect Network Type
    signal_result = executor.execute(f"uqmi -d {qmi_device} --get-signal-info")

    if signal_result.failed:
        raise AssertionError(
            f"Failed to get signal info on {device_name}\n"
            f"stdout: {signal_result.stdout}\n"
            f"stderr: {signal_result.stderr}"
        )

    signal_out = signal_result.stdout.lower()

    if "nr5g" in signal_out:
        network_type = "5G"
    elif "lte" in signal_out:
        network_type = "4G"
    else:
        raise AssertionError(
            f"Connected but unknown network type detected:\n{signal_result.stdout}"
        )

    log_message(f"{interface} is connected to {network_type}")

    # Step 3: Get IP Address
    ip_result = executor.execute(f"uqmi -d {qmi_device} --get-current-settings")

    if ip_result.failed:
        raise AssertionError(
            f"Failed to get modem IP on {device_name}\n"
            f"stdout: {ip_result.stdout}\n"
            f"stderr: {ip_result.stderr}"
        )

    match = re.search(r'"ip":\s*"(\d+\.\d+\.\d+\.\d+)"', ip_result.stdout)

    if match:
        ip = match.group(1)
        log_message(f"Detected modem IP: {ip}")
        return ip

    raise AssertionError(
        f"Modem connected but IP not detected.\nOutput:\n{ip_result.stdout}"
    )    
  
 
 
@keyword("Ensure WWAN Default Route")
def ensure_wwan_default_route(device_name, iface="wwan0", modem_ip=None):

    executor = get_registered_executor(device_name)

    result = executor.execute("ip route show default")
    route_out = result.stdout.strip()

    log_message(f"Current default routes:\n{route_out}")

    if route_out and f" dev {iface}" in route_out:
        log_message(f"{iface} is already a default route.")
        return True
   
    if modem_ip:
        executor.execute(
            f"ip route add default via {modem_ip} dev {iface} metric 100 || true"
        )
    else:
        executor.execute(
            f"ip route add default dev {iface} metric 100 || true"
        )

    log_message(f"Added preferred default route via {iface} (metric 100)")

    return True

# ============================================================
# WIFI
# ============================================================
@keyword("Setup WiFi AP")
def setup_wifi_ap(device_name, ssid, password, encryption="psk2"):
 
    executor = get_registered_executor(device_name)
    log_message(f"[STEP]: Setting up WiFi AP '{ssid}' on {device_name}...")

    # Check if SSID exists
    result = executor.execute(f"uci show wireless | grep \".ssid='{ssid}'\"")
    output = result.stdout.strip()

    if output:
        log_message(f"SSID '{ssid}' already exists. Updating settings...")
        matches = re.findall(r"(wireless\.(?:@wifi-iface\[\d+\]|wifinet\d+))\.ssid", output)
        for iface_index in matches:
            cmds = [
                f"uci set {iface_index}.device='radio0'",
                f"uci set {iface_index}.mode='ap'",
                f"uci set {iface_index}.encryption='{encryption}'",
                f"uci set {iface_index}.key='{password}'",
                f"uci set {iface_index}.network='lan'",
                f"uci set {iface_index}.disabled='0'",
            ]
            for cmd in cmds:
                log_message(f"[CMD] {cmd}")
                executor.execute(cmd)

        executor.execute("uci commit wireless && wifi reload")
        log_message(f"SSID '{ssid}' updated successfully.")
        return True

    # Otherwise, create new AP
    log_message(f"Creating new SSID '{ssid}'...")
    cmds = [
        "uci add wireless wifi-iface",
        "uci set wireless.@wifi-iface[-1].device='radio0'",
        "uci set wireless.@wifi-iface[-1].mode='ap'",
        f"uci set wireless.@wifi-iface[-1].ssid='{ssid}'",
        f"uci set wireless.@wifi-iface[-1].encryption='{encryption}'",
        f"uci set wireless.@wifi-iface[-1].key='{password}'",
        "uci set wireless.@wifi-iface[-1].network='lan'",
        "uci set wireless.@wifi-iface[-1].disabled='0'",
        "uci commit wireless",
        "wifi reload",
    ]
    for cmd in cmds:
        log_message(f"[CMD] {cmd}")
        executor.execute(cmd)

    log_message(f"[OK]: SSID '{ssid}' created and enabled successfully.")
    return True


@keyword("Connect RPis To WiFi")
def connect_rpis_to_wifi(device_names, ssid, password):

    log_message("=== START: Connect RPis To WiFi ===")

    if isinstance(device_names, str):
        device_names = [device_names]

    results = {}
    failed_devices = []

    for device_name in device_names:

        executor = get_registered_executor(device_name)

        if executor is None:
            raise AssertionError(f"No executor registered for device '{device_name}'")
        success = False

        for attempt in range(1, MAX_RETRIES + 1):

            log_message(f"[{device_name}]: Attempt {attempt}/{MAX_RETRIES}")

            executor.execute("sudo nmcli dev wifi rescan || true")

            log_message(f"[{device_name}]: Executing: sudo nmcli dev wifi list" )

            scan_res = executor.execute("sudo nmcli dev wifi list")

            log_message(f"[{device_name}] Output:\n{scan_res.stdout}")

            # Check if SSID exists in scan
            if ssid not in scan_res.stdout:
                log_message(f"[{device_name}] SSID '{ssid}' not found. Retrying...")
                time.sleep(5)
                continue

            log_message(f"[{device_name}]: Trying to connect to SSID '{ssid}'...")

            connect_cmd = (f"sudo nmcli dev wifi connect '{ssid}' password '{password}'")

            # log_message(f"[CUSTOM LOG] {device_name}: Executing: {connect_cmd}")

            res = executor.execute(connect_cmd)

            log_message(f"[{device_name}] Output:\n{res.stdout}")

            if res.stderr:
                log_message(f"[{device_name}] Error:\n{res.stderr}")

            verify = executor.execute("nmcli -t -f ACTIVE,SSID dev wifi | grep '^yes:' || true")

            if f"yes:{ssid}" in verify.stdout:
                log_message(f"[{device_name}]: Connected to WiFi SSID '{ssid}' successfully.")
                success = True
                break
            else:
                log_message(f"[{device_name}]: Connection failed. Retrying...")
                time.sleep(5)

        results[device_name] = success

        if not success:
            failed_devices.append(device_name)
            log_message(f"[{device_name}]: Failed after {MAX_RETRIES} attempts.")

    log_message("=== END: Connect RPis To WiFi ===")

    if failed_devices:
        raise AssertionError(f"Failed to connect devices: {', '.join(failed_devices)}" )
    return results




# ============================================================
# RPI CONNECTIVITY
# ============================================================

def _auto_detect_interface(executor):
    result = executor.execute("ip -o link show | awk -F': ' '{print $2}' | grep -v lo")

    interfaces = result.stdout.strip().split()

    # Prefer eth over wlan automatically
    for iface in interfaces:
        if iface.startswith("eth"):
            return iface

    for iface in interfaces:
        if iface.startswith("wlan"):
            return iface

    raise RuntimeError("No usable interface detected")


@keyword("Check RPi Routing Dynamic")
def check_rpi_routing_dynamic(device_name, preferred_iface=None):

    executor = get_registered_executor(device_name)

    iface = preferred_iface or _auto_detect_interface(executor)

    log_message(f"[STEP]: {device_name}: Using interface {iface}")

    result = executor.execute("ip route show | grep '^default'")
    out = result.stdout.strip()

    if iface in out:
        log_message(f"{device_name}: Already has default route via {iface}")
        return True  

    result = executor.execute(f"ip -4 addr show dev {iface} | grep 'inet '")
    gw_out = result.stdout.strip()

    match = re.search(r'inet (\d+\.\d+\.\d+)\.\d+', gw_out)

    if match:
        gw = f"{match.group(1)}.1"

        # Clean old default routes
        # executor.execute("sudo ip route del default || true")
        # Add new default route
        executor.execute(f"sudo ip route add default via {gw} dev {iface}")

        log_message(f"[OK]: {device_name}: Added default route via {gw} dev {iface}")
        return True

    else:raise AssertionError(f"{device_name}: Failed to configure routing for {iface}")
    



@keyword("Ping All RPis")
def ping_all_rpis(pc_name, iface, remote_ip, duration=10):

    log_message(f"[STEP]: Pinging {remote_ip} from {pc_name} via {iface}")

    executor = get_registered_executor(pc_name)

    # res = executor.execute(f"ping -I {iface} -c 5 -W {duration} {remote_ip}")
    res = executor.execute(f"ping -c 5 -W {duration} {remote_ip}")

    log_message(f"[PING OUTPUT]\n{res.stdout}")

    if res.stderr:
        log_message(f"[PING ERROR]\n{res.stderr}")

    if "100% packet loss" in res.stdout or res.failed:
        raise AssertionError(f"{pc_name}: Ping failed to {remote_ip}")

    log_message(f"[OK] {pc_name}: Ping via {iface} successful")

    return True


     
@keyword("Cleanup WWAN Default Route")
def cleanup_wwan_default_route(device_name, iface="wwan0", modem_ip=None):
    executor = get_registered_executor(device_name)
    log_message(f"[STEP] Cleaning WWAN {iface} default route")
    if modem_ip:
        executor.execute(f"ip route del default via {modem_ip} dev {iface} || true")
    else:
        executor.execute(f"ip route del default dev {iface} || true")
 
    log_message(f"[OK]:{device_name}: WWAN {iface} default route cleaned")    
    
 
    
    
@keyword("Start Moniter System Stats")    
def moniter_sys_stats(device, duration):
    monitor_system_stats_around_iperf (device, duration)
    
@keyword("Stop Moniter System Stats")    
def stop_moniter_sys_stats():
    wait_for_monitoring_to_finish     