# START_DESCRIPTION 
#1. Initialize logging and establish connections to DUT & to both RPi's 
#2. Check the DUT connection, signal information and default route.
#3. Configure Two Wi-Fi on DUT.
#4. Configure both the RPi for Wi-Fi AP.
#5. Baseline connectivity check via ping & collect the latency.
#6. Print baseline stats on DUT (CPU, memory used, interrupts).
#7. Check RPis routing and connectivity.
#8. Keep printing baseline stats on DUT while test is running (CPU, memory used, interrupts)
#9. Collect logs/results
#10. Print baseline stats on DUT after test completion (CPU, memory used, interrupts)
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

MAX_RETRIES = 5

# ============================================================
# HELPER FUNTION
# ==========================================================

def _auto_detect_interface(executor):
  
    result = executor.execute("ip -o link show | awk -F': ' '{print $2}' | grep -v lo" )

    interfaces = result.stdout.strip().split()

    # Prefer eth over wlan automatically
    for iface in interfaces:
        if iface.startswith("eth"):
            return iface

    for iface in interfaces:
        if iface.startswith("wlan"):
            return iface

    raise RuntimeError("No usable interface detected")

# ============================================================
# MODEM / WWAN
# ===========================================================

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





@keyword("Setup WiFi AP")
def setup_wifi_ap(device_name, wifi_list):
    
    executor = get_registered_executor(device_name)

    if isinstance(wifi_list, str):
        wifi_list = json.loads(wifi_list)

    log_message(f"Configuring {len(wifi_list)} SSIDs on {device_name}...")

    for wifi in wifi_list:
        ssid = wifi["ssid"]
        password = wifi["password"]
        encryption = wifi.get("encryption", "psk2")

        log_message(f"Setting up SSID '{ssid}'...")

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

        else:
            log_message(f"Creating SSID '{ssid}'...")

            cmds = [
                "uci add wireless wifi-iface",
                "uci set wireless.@wifi-iface[-1].device='radio0'",
                "uci set wireless.@wifi-iface[-1].mode='ap'",
                f"uci set wireless.@wifi-iface[-1].ssid='{ssid}'",
                f"uci set wireless.@wifi-iface[-1].encryption='{encryption}'",
                f"uci set wireless.@wifi-iface[-1].key='{password}'",
                "uci set wireless.@wifi-iface[-1].network='lan'",
                "uci set wireless.@wifi-iface[-1].disabled='0'",
            ]
            for cmd in cmds:
                log_message(f"[CMD] {cmd}")
                executor.execute(cmd)

    executor.execute("uci commit wireless")
    executor.execute("wifi reload")

    log_message("All SSIDs configured successfully.")
    return True




@keyword("Connect RPi To WiFi")
def connect_rpi_to_wifi(rpi_list, wifi_list_or_ssid, password=None):

    log_message("=== START Connect_RPi_To_WiFi ===")
    time.sleep(8)

    results = {}
    failed = []

    # Convert Robot PC list → executor dict
    rpi_connections = {}

    for pc in rpi_list:
        name = pc["name"]
        executor = get_registered_executor(name)

        if executor is None:
            raise AssertionError(f"No executor registered for {name}")

        rpi_connections[name] = executor

 
    # CASE 1: SAME SSID FOR ALL
    if isinstance(wifi_list_or_ssid, str):

        ssid = wifi_list_or_ssid

        for name, executor in rpi_connections.items():
            
            log_message(f"{name}: Scanning WiFi networks...")
            log_message(f"{name}: Executing: sudo nmcli dev wifi list")
            scan_res = executor.execute("sudo nmcli dev wifi list")

            # log_message(f"{name}: Scan Output:\n{scan_res.stdout}")
            if scan_res.stderr:
                log_message(f"{name}: Scan Error:\n{scan_res.stderr}")

            if ssid not in (scan_res.stdout or ""):
                log_message(f"{name}: SSID '{ssid}' NOT FOUND in scan")
                results[name] = False
                failed.append(name)
                continue
            
            log_message(f"{name}: Connecting to SSID '{ssid}'...")
            connect_cmd = f"sudo nmcli dev wifi connect '{ssid}' password '{password}'"
            # log_message(f"{name}: Executing: {connect_cmd}")

            result = executor.execute(connect_cmd)

            log_message(f"{name}: Connect STDOUT:\n{result.stdout}")
            if result.stderr:
                log_message(f"{name}: Connect STDERR:\n{result.stderr}")

            success = "successfully activated" in (result.stdout or "").lower()

            # Verify active connection
            verify = executor.execute(
                "nmcli -t -f ACTIVE,SSID dev wifi | grep '^yes:' || true"
            )
            log_message(f"{name}: Verification Output:\n{verify.stdout}")

            if success and f"yes:{ssid}" in (verify.stdout or ""):
                log_message(f"{name}: Connected to SSID '{ssid}' successfully.")
                results[name] = True
            else:
                log_message(f"{name}: Connection verification failed.")
                results[name] = False
                failed.append(name)

   
    # CASE 2: ONE SSID PER RPI
    elif isinstance(wifi_list_or_ssid, list):

        rpi_names = list(rpi_connections.keys())

        if len(wifi_list_or_ssid) < len(rpi_names):
            raise AssertionError("Not enough WiFi profiles for number of RPis")

        for index, name in enumerate(rpi_names):

            executor = rpi_connections[name]
            wifi = wifi_list_or_ssid[index]

            ssid = wifi["ssid"]
            pw = wifi["password"]
            
            log_message(f"{name}: Scanning WiFi networks...")
            log_message(f"{name}: Executing: sudo nmcli dev wifi list")
            scan_res = executor.execute("sudo nmcli dev wifi list")

            # log_message(f"{name}: Scan Output:\n{scan_res.stdout}")
            if scan_res.stderr:
                log_message(f"{name}: Scan Error:\n{scan_res.stderr}")

            if ssid not in (scan_res.stdout or ""):
                log_message(f"{name}: SSID '{ssid}' NOT FOUND in scan")
                results[name] = False
                failed.append(name)
                continue
            
            log_message(f"{name}: Connecting to SSID '{ssid}'...")
            connect_cmd = f"sudo nmcli dev wifi connect '{ssid}' password '{pw}'"
            # log_message(f"{name}: Executing: {connect_cmd}")

            result = executor.execute(connect_cmd)

            log_message(f"{name}: Connect STDOUT:\n{result.stdout}")
            if result.stderr:
                log_message(f"{name}: Connect STDERR:\n{result.stderr}")

            success = "successfully activated" in (result.stdout or "").lower()

            verify = executor.execute(
                "nmcli -t -f ACTIVE,SSID dev wifi | grep '^yes:' || true"
            )
            log_message(f"{name}: Verification Output:\n{verify.stdout}")

            if success and f"yes:{ssid}" in (verify.stdout or ""):
                log_message(f"{name}: Connected to SSID '{ssid}' successfully.")
                results[name] = True
            else:
                log_message(f"{name}: Connection verification failed.")
                results[name] = False
                failed.append(name)

    else:
        raise ValueError("Invalid WiFi input")

    log_message("=== END Connect_RPi_To_WiFi ===")

    if failed:
        raise AssertionError(f"WiFi failed on: {', '.join(failed)}")

    return results



@keyword("Check RPi Routing Dynamic")
def check_rpi_routing_dynamic(rpi_list, preferred_iface=None):

    for pc in rpi_list:

        name = pc["name"]
        executor = get_registered_executor(name)

        if executor is None:
            raise AssertionError(f"No executor registered for {name}")

        iface = preferred_iface or _auto_detect_interface(executor)

        log_message(f"{name}: Using interface {iface}")

        result = executor.execute("ip route show | grep '^default' || true")
        out = result.stdout.strip()

        log_message(f"{name}: Current default route -> {out}")

        if iface in out:
            log_message(f"{name}: Already has default route via {iface}")
            continue

        result = executor.execute(
            f"ip -4 addr show dev {iface} | grep 'inet ' || true"
        )
        gw_out = result.stdout.strip()

        log_message(f"{name}: IP info -> {gw_out}")

        match = re.search(r'inet (\d+\.\d+\.\d+)\.\d+', gw_out)

        if not match:
            raise AssertionError(
                f"{name}: Failed to detect IP address on {iface}"
            )

        gw = f"{match.group(1)}.1"

        executor.execute("sudo ip route del default || true")
        executor.execute(f"sudo ip route add default via {gw} dev {iface}")

        log_message(f"{name}: Added default route via {gw} dev {iface}")

    return True




@keyword("Ping All RPis")
def Ping_All_RPis(rpi_list, remote_ip="8.8.8.8", iface_name=None):

    results = {}
    iface_ips = {}
    threads = []
    lock = threading.Lock()
    resolved_connections = {}

    for pc in rpi_list:
        name = pc["name"]
        executor = get_registered_executor(name)

        if executor is None:
            raise AssertionError(f"No executor registered for {name}")

        resolved_connections[name] = executor
        
    for name, executor in resolved_connections.items():

        iface = iface_name if iface_name else _auto_detect_interface(executor)

        log_message(f"[{name}] Using interface: {iface}")

        res = executor.execute(
            f"ip -4 addr show {iface} | grep -oP '(?<=inet\\s)\\d+(\\.\\d+){{3}}' || true"
        )

        ip = res.stdout.strip()

        log_message(f"[{name}] IP detection raw output: {res.stdout}")

        if ip:
            iface_ips[name] = {"iface": iface, "ip": ip}
            log_message(f"[{name}] Interface {iface} IP = {ip}")
        else:
            iface_ips[name] = {"iface": iface, "ip": None}
            log_message(f"[{name}] Failed to detect IP on {iface}")

    def ping_worker(name, executor):

        local_results = []
        iface = iface_ips[name]["iface"]
        local_ip = iface_ips[name]["ip"]

        if not local_ip:
            with lock:
                results[name] = {
                    "status": False,
                    "details": [f"[{name}] No IP detected on {iface}"]
                }
            return

        # Ping Remote
        log_message(f"[{name}] Pinging remote {remote_ip} via {iface}")

        # res = executor.execute(f"ping -I {iface} -c 4 -w 10 {remote_ip} || true")
        res = executor.execute(f"ping  -c 4 -w 10 {remote_ip} || true")

        out = res.stdout
        log_message(f"[{name}] Remote ping output:\n{out}")

        status_remote = " 0% packet loss" in out

        local_results.append(
            f"[{name}] → Remote {remote_ip}: {'OK' if status_remote else 'FAIL'}"
        )

        # Ping Peers
        status_peers = True

        for peer_name, peer_data in iface_ips.items():
            if peer_name == name:
                continue

            peer_ip = peer_data["ip"]
            if not peer_ip:
                continue

            log_message(f"[{name}] Pinging {peer_name} ({peer_ip})")

            # res_peer = executor.execute(f"ping -I {iface} -c 4 -w 10 {peer_ip} || true")
            res_peer = executor.execute(f"ping -c 4 -w 10 {peer_ip} || true")

            out_peer = res_peer.stdout
            log_message(f"[{name}] Peer {peer_name} ping output:\n{out_peer}")

            ok = " 0% packet loss" in out_peer
            status_peers = status_peers and ok

            local_results.append(
                f"[{name}] → {peer_name} ({peer_ip}): {'OK' if ok else 'FAIL'}"
            )

        with lock:
            results[name] = {
                "status": status_remote and status_peers,
                "details": local_results,
            }

 
    for name, executor in resolved_connections.items():
        t = threading.Thread(
            target=ping_worker,
            args=(name, executor)
        )
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    failed = [name for name, r in results.items() if not r["status"]]

    if failed:
        log_message(f"Ping tests failed for RPis: {', '.join(failed)}")
        raise AssertionError(
            f"One or more RPis failed ping tests: {', '.join(failed)}"
        )

    log_message("All RPis pinged remote IP and peers successfully.")

    return results




@keyword("Cleanup WWAN Default Route")
def cleanup_wwan_default_route(device_name, iface="wwan0", modem_ip=None):
    executor = get_registered_executor(device_name)
 
    if modem_ip:
        executor.execute(f"ip route del default via {modem_ip} dev {iface} || true")
    else:
        executor.execute(f"ip route del default dev {iface} || true")
 
    log_message(f"{device_name}: WWAN default route cleaned")    


@keyword("Start Moniter System Stats")    
def moniter_sys_stats(device, duration):
    monitor_system_stats_around_iperf (device, duration)
    
@keyword("Stop Moniter System Stats")    
def stop_moniter_sys_stats():
    wait_for_monitoring_to_finish  
    