import paramiko
import time
import re
import os
import threading
from datetime import datetime
from robot.api.deco import keyword
from robot.libraries.BuiltIn import BuiltIn

_log_lock = threading.Lock()
_log_file = None
_metrics_threads = {}

# Global max retries
MAX_RETRIES = 3

# ----------------------
# Custom Logging
# ----------------------
@keyword("Initialize Custom Log File")
def initialize_custom_log_file():
    global _log_file
    log_folder = BuiltIn().get_variable_value("${LOG_FOLDER}", default="logs")
    os.makedirs(log_folder, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    _log_file = os.path.join(log_folder, f"custom_log_{timestamp}.log")

    with open(_log_file, "w") as f:
        f.write(f"Custom log started at {timestamp}\n")

    Log_Message_To_Custom_File(f"[INFO] Custom log initialized: {_log_file}")
    return _log_file


@keyword
def Log_Message_To_Custom_File(message: str):
    global _log_file
    if not _log_file:
        log_folder = BuiltIn().get_variable_value("${LOG_FOLDER}", default="logs")
        os.makedirs(log_folder, exist_ok=True)
        _log_file = os.path.join(log_folder, "default_custom.log")

    safe_message = message.replace("${", "$${")  # avoid Robot expansion
    with _log_lock:
        with open(_log_file, "a") as f:
            f.write(safe_message + "\n")

    BuiltIn().log_to_console(f"[CUSTOM LOG] {safe_message}")


# ----------------------
# SSH Utilities
# ----------------------
def _ssh_connect(dev):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(dev["ip"], username=dev["user"], password=dev["password"],
                look_for_keys=False, allow_agent=False, banner_timeout=60)
    Log_Message_To_Custom_File(f"SSH connection established to {dev['ip']}")
    return ssh

def _ssh_exec(ssh, cmd, host="Device"):
    Log_Message_To_Custom_File(f"{host}: Executing: {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        Log_Message_To_Custom_File(f"{host} Output:\n{out}")
    if err:
        Log_Message_To_Custom_File(f"{host} Error:\n{err}")
    return out, err

def strip_cidr(ip):
    """Remove /xx from CIDR if present."""
    return ip.split("/")[0] if ip else ip
# ----------------------
# Keywords
# ----------------------
@keyword
def Connect_Device(dev):
    ssh = _ssh_connect(dev)
    Log_Message_To_Custom_File(f"Connected to {dev['ip']}")
    return ssh


# ----------------------
# BB Modem / Network Utilities
# ----------------------

@keyword
def Ensure_Modem_Connected(bb_dev, bb_ssh):
    Log_Message_To_Custom_File("Checking modem connection...")
    for attempt in range(1, MAX_RETRIES + 1):
        status, _ = _ssh_exec(bb_ssh, "uqmi -d /dev/cdc-wdm0 --get-data-status", "BB")
        #status = status.strip().lower()
        status = status.strip().strip('"')
 
        if status == "connected":
            Log_Message_To_Custom_File("Modem is connected.")
            return True
        else:
            Log_Message_To_Custom_File(f"Attempt {attempt}/{MAX_RETRIES}: Modem disconnected, retrying...")
            _ssh_exec(bb_ssh, "ifup Modem1 && ifup Modem2", "BB")
            time.sleep(60)

    raise AssertionError("Modem failed to connect after max retries")

@keyword
def Get_Modem_IP(bb_ssh):
    out, _ = _ssh_exec(bb_ssh, "uqmi -d /dev/cdc-wdm0 --get-current-settings", "BB")
    match = re.search(r'"ip":\s*"(\d+\.\d+\.\d+\.\d+)"', out)
    if match:
        ip = match.group(1)
        Log_Message_To_Custom_File(f"Detected modem IP: {ip}")
        return ip
    raise AssertionError("Could not parse modem IP")



@keyword
def Check_Signal_Info(bb_ssh):
    out, _ = _ssh_exec(bb_ssh, "uqmi -d /dev/cdc-wdm0 --get-signal-info", "BB")
    if "nr5g" in out.lower():
        Log_Message_To_Custom_File("Connected to 5G")
        return "5G"
    elif "lte" in out.lower():
        Log_Message_To_Custom_File("Connected to 4G")
        return "4G"
    raise AssertionError(f"Unknown or no network type detected: {out}")
    
    
#-------------------------
# Set VxLAN Interface on BB and RPis
#---------------------------
@keyword
def Setup_VXLAN_Interface(bb_ssh,vxlan_name,vxlan_id,underlay_iface,dstport,bridge_name,overlay_ip=None):
    """
    Configure VXLAN on BB:
      0. Clean up existing VXLAN interface (if any).
      1. Create VXLAN interface bound to underlay interface (e.g., wwan0).
      2. Attach VXLAN to bridge (e.g., br-lan).
      3. Assign overlay IP to bridge (optional).
      4. Bring VXLAN interface up.
    """

    Log_Message_To_Custom_File(f"--- START Setup_VXLAN_Interface: {vxlan_name} on {underlay_iface} ---")

    # 0. Cleanup existing VXLAN
    cleanup_cmds = [
       # f"ip addr del {overlay_ip} dev {bridge_name} || true" if overlay_ip else "",
       # f"brctl delif {bridge_name} {vxlan_name} || true",
        f"ip link set {vxlan_name} down || true",
        f"ip link delete {vxlan_name} || true",
    ]
    for cmd in cleanup_cmds:
        if cmd.strip():
            _ssh_exec(bb_ssh, cmd, "BB")

    # 1. Create VXLAN interface
    cmd_create = (
        f"ip link add {vxlan_name} type vxlan id {vxlan_id} "
        f"dev {underlay_iface} dstport {dstport} || true"
    )
    _ssh_exec(bb_ssh, cmd_create, "BB")

    # 2. Add VXLAN to bridge
    cmd_bridge = f"brctl addif {bridge_name} {vxlan_name} || true"
    _ssh_exec(bb_ssh, cmd_bridge, "BB")

    # 3. Assign overlay IP to bridge
    if overlay_ip:
        cmd_ip = (
            f"ip addr show dev {bridge_name} | grep -q '{overlay_ip}' "
            f"|| ip addr add {overlay_ip} dev {bridge_name}"
        )
        _ssh_exec(bb_ssh, cmd_ip, "BB")

    # 4. Bring VXLAN interface up
    cmd_up = f"ip link set {vxlan_name} up"
    _ssh_exec(bb_ssh, cmd_up, "BB")

    Log_Message_To_Custom_File(f"--- END Setup_VXLAN_Interface: {vxlan_name} ---")
    return True

    
@keyword
def Setup_RPi_VXLANs(rpi_connections, vxlan_list, modem_ip):
    """
    Configure VXLAN interfaces on all RPis based on vxlan_list.
    - rpi_connections: dict from Connect_All_RPis (name -> (ssh, rpi_info))
    - vxlan_list: list of vxlan config dicts from TEST_JSON["vxlan"]
    - modem_ip: remote BB underlay IP (from Get_Modem_IP)
    """

    threads = []
    errors = []

    def setup_worker(rpi_name, ssh, vxlan_cfg):
        vxlan_name = vxlan_cfg["vxlan_name"]
        vxlan_id = vxlan_cfg["vxlan_id"]
        underlay_iface = vxlan_cfg["underlay_iface"]
        dstport = vxlan_cfg["dstport"]
        overlay_ip = vxlan_cfg["overlay_ip"]

        try:
            Log_Message_To_Custom_File(f"[{rpi_name}] Cleaning old VXLAN: {vxlan_name}")
            cmds_cleanup = [
                f"sudo ip addr del {overlay_ip} dev {vxlan_name} 2>/dev/null || true",
                f"sudo ip link set {vxlan_name} down 2>/dev/null || true",
                f"sudo ip link delete {vxlan_name} 2>/dev/null || true",
            ]

            cmds_create = [
                f"sudo ip link add {vxlan_name} type vxlan id {vxlan_id} "
                f"dev {underlay_iface} remote {modem_ip} dstport {dstport}",
                f"sudo ip addr add {overlay_ip} dev {vxlan_name}",
                f"sudo ip link set {vxlan_name} up",
            ]

            for cmd in cmds_cleanup + cmds_create:
                _ssh_exec(ssh, cmd, rpi_name)

            Log_Message_To_Custom_File(f"[{rpi_name}] VXLAN {vxlan_name} setup complete with IP {overlay_ip}")

        except Exception as e:
            errors.append(f"{rpi_name} failed VXLAN setup: {e}")

    # Launch setup threads (parallel for each RPi and vxlan entry)
    for (rpi_name, (ssh, rpi_info)), vxlan_cfg in zip(rpi_connections.items(), vxlan_list):
        t = threading.Thread(target=setup_worker, args=(rpi_name, ssh, vxlan_cfg))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    if errors:
        raise AssertionError(f"One or more RPi VXLAN setups failed: {errors}")
    return True


@keyword
def cleanup_bb_vxlan(bb_ssh, vxlan_name, bridge_name, overlay_ip=None):
    """
    Cleanup VXLAN and bridge config on BB.
    """
    Log_Message_To_Custom_File(f"--- START cleanup_bb_vxlan: {vxlan_name} ---")

    cmds = [
        f"ip addr del {overlay_ip} dev {bridge_name} || true" if overlay_ip else "",
        f"brctl delif {bridge_name} {vxlan_name} || true",
        f"ip link set {vxlan_name} down || true",
        f"ip link delete {vxlan_name} || true"
    ]
    for cmd in cmds:
        if cmd.strip():
            _ssh_exec(bb_ssh, cmd, "BB")

    Log_Message_To_Custom_File(f"--- END cleanup_bb_vxlan: {vxlan_name} ---")
    return True 
    
@keyword
def cleanup_rpis_vxlan(rpi_connections):
    """
    Removes VXLAN interfaces from all RPis.
    rpi_connections: dict {name: (ssh, config)} where config contains vxlan_name.
    """
    for name, (ssh, rpi) in rpi_connections.items():
        vxlan = rpi.get("vxlan_name", "vxlan100")
        cmds = [
            f"sudo ip link set {vxlan} down || true",
            f"sudo ip link delete {vxlan} type vxlan || true"
        ]

        for cmd in cmds:
            _ssh_exec(ssh, cmd, name)
            Log_Message_To_Custom_File(f"{name} cleanup: executed {cmd}")

# ----------------------
# Multi-RPi Utilities
# ----------------------
@keyword
def Connect_All_RPis(rpi_list):
    """
    Connect multiple RPis in parallel.
    rpi_list can be:
      - list of dicts → each dict is RPi info (name defaults to 'RPi1', 'RPi2', ...)
      - list of (name, dict) tuples → uses name in logs
    Returns dict of SSH connections keyed by name.
    """
    connections = {}
    threads = []
    errors = []

    def connect_worker(name, rpi):
        try:
            ssh = _ssh_connect(rpi)
            Log_Message_To_Custom_File(f"Connected to {name} ({rpi['ip']})")
            connections[name] = (ssh, rpi)
        except Exception as e:
            errors.append(f"{name} failed: {e}")

    for idx, entry in enumerate(rpi_list, start=1):
        if isinstance(entry, tuple):
            name, rpi = entry
        else:
            rpi = entry
            name = rpi.get("name", f"RPi{idx}")
        t = threading.Thread(target=connect_worker, args=(name, rpi))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    if errors:
        raise AssertionError(f"One or more RPis failed to connect: {errors}")
    return connections

@keyword
def Check_RPi_Routing_Dynamic(rpi_connections):
    """Checks and sets default route for all RPis using their specified interface."""
    results = {}
    for name, (ssh, rpi) in rpi_connections.items():
        iface = rpi.get('interface', 'eth1')
        out, _ = _ssh_exec(ssh, "ip route show | grep '^default'", name)
        if iface in out:
            Log_Message_To_Custom_File(f"{name}: Already has default route via {iface}")
            continue

        gw_out, _ = _ssh_exec(ssh, f"ip -4 addr show dev {iface} | grep 'inet '", name)
        match = re.search(r'inet (\d+\.\d+\.\d+)\.\d+', gw_out)
        if match:
            gw = f"{match.group(1)}.1"
            _ssh_exec(ssh, f"sudo ip route add default via {gw} dev {iface}", name)
            Log_Message_To_Custom_File(f"{name}: Added default route via {gw}")
        else:
            raise AssertionError(f"{name}: Failed to configure routing for {iface}")
    return True



@keyword
def Ping_All_RPis_VXLAN(rpi_connections, vxlan_list, bb_overlay_ip):
    """
    Each RPi pings:
      1. The BB VXLAN IP (bb_overlay_ip)
      2. Every other RPi's VXLAN IP (from vxlan_list)

    Returns dict of {RPiName: {"status": True/False, "details": list of results}}.
    Raises AssertionError if any RPi fails ping tests.
    """
    results = {}
    threads = []
    lock = threading.Lock()

    # Step 0: Build mapping RPi -> VXLAN overlay IP (strip /xx if present)
    vxlan_ips = {}
    for (rpi_name, _), vxlan_cfg in zip(rpi_connections.items(), vxlan_list):
        vxlan_ips[rpi_name] = strip_cidr(vxlan_cfg.get("overlay_ip"))

    bb_ip = strip_cidr(bb_overlay_ip)

    def ping_worker(name, conn, peers, bb_ip):
        ssh, rpi = conn
        local_results = []

        # 1. Ping BB VXLAN
        out, _ = _ssh_exec(ssh, f"ping -c 4 -w 10 {bb_ip}", name)
        status_bb = not ("100% packet loss" in out or "Unreachable" in out)
        local_results.append(
            f"[{name}] → BB VXLAN {bb_ip}: {'OK' if status_bb else 'FAIL'}\n{out}"
        )

        # 2. Ping each peer RPi VXLAN
        status_peers = True
        for peer_name, peer_ip in peers.items():
            if peer_name == name or not peer_ip:
                continue
            out_peer, _ = _ssh_exec(ssh, f"ping -c 4 -w 10 {peer_ip}", name)
            ok = not ("100% packet loss" in out_peer or "Unreachable" in out_peer)
            status_peers = status_peers and ok
            local_results.append(
                f"[{name}] → {peer_name} VXLAN {peer_ip}: {'OK' if ok else 'FAIL'}\n{out_peer}"
            )

        # Collect into global results
        with lock:
            results[name] = {
                "status": status_bb and status_peers,
                "details": local_results,
            }

    # Step 1: Launch threads for each RPi
    for name, conn in rpi_connections.items():
        t = threading.Thread(target=ping_worker, args=(name, conn, vxlan_ips, bb_ip))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    # Step 2: Final summary + Assertion
    failed = [name for name, r in results.items() if not r["status"]]
    if failed:
        Log_Message_To_Custom_File(f"VXLAN ping tests failed for RPis: {', '.join(failed)}")
        raise AssertionError(f"One or more RPis failed VXLAN ping tests: {', '.join(failed)}")

    Log_Message_To_Custom_File("All RPis pinged BB VXLAN and peer VXLANs successfully.")
    return results


# ----------------------
# Metrics / Reboot Utilities
# ----------------------

def _metrics_worker(bb_ssh, interval, stop_event):
    while not stop_event.is_set():
        try:
            cmd = (
                'echo "=== SYSTEM SNAPSHOT ==="; '
                'uptime; '
                'sar -u 1 1; '
                'free -m; '
                'cat /proc/interrupts '
            )
            out, _ = _ssh_exec(bb_ssh, cmd, "BB")
            Log_Message_To_Custom_File(f"Live system metrics:\n{out}")  
            time.sleep(interval)
        except Exception as e:
            Log_Message_To_Custom_File(f"Metrics polling error: {e}")
            break

@keyword
def Log_System_Metrics(bb_ssh, interval=10):
    stop_event = threading.Event()
    thread = threading.Thread(target=_metrics_worker, args=(bb_ssh, interval, stop_event), daemon=True)
    thread.start()
    tid = id(thread)
    _metrics_threads[tid] = stop_event
    Log_Message_To_Custom_File(f"Started live metrics logging thread (ID: {tid})")
    return tid


@keyword
def Stop_System_Metrics(tid):
    stop_event = _metrics_threads.get(tid)
    if not stop_event:
        Log_Message_To_Custom_File(f"No live metrics thread found with ID {tid}")
        return
    stop_event.set()
    Log_Message_To_Custom_File(f"Stopped live metrics logging thread (ID: {tid})")


@keyword
def Collect_Baseline_Metrics(bb_ssh, remote_ip="8.8.8.8", duration=10):
    out, _ = _ssh_exec(bb_ssh, f"ping -c {duration} -I wwan0 {remote_ip}", "BB")
    if "100% packet loss" in out or not out:
        raise AssertionError(f"Baseline ping failed:\n{out}")
        
    cmd = (
        'echo "System load:" && uptime && '
        'echo "\\nCPU usage:" && sar -u 1 1 && '
        'echo "\\nMemory usage:" && free -m && '
        'echo "\\nInterrupts:" && cat /proc/interrupts '
    )
    #cmd = "uptime && sar -u 1 1 && free -m && cat /proc/interrupts"
    out, _ = _ssh_exec(bb_ssh, cmd, "BB")
    Log_Message_To_Custom_File(f"Baseline metrics:\n{out}")
 

@keyword
def Cleanup_RPi_Default_Route(rpi_connections):
    """
    Remove default routes on RPis for their specified interface (default: eth1).
    If multiple defaults exist via that iface, remove them all.
    """
    results = {}
    for name, (ssh, rpi) in rpi_connections.items():
        iface = rpi.get("interface", "eth1")
        Log_Message_To_Custom_File(f"--- START Cleanup_RPi_Default_Route for {name} ({iface}) ---")

        # Get all default routes via this iface
        route_out, _ = _ssh_exec(ssh, f"ip route show | grep '^default .* dev {iface}'", name)
        if not route_out.strip():
            Log_Message_To_Custom_File(f"{name}: No default routes found via {iface}")
            results[name] = "No routes to delete"
            continue

        # Delete each default route found
        cleanup_cmd = (
            f"ip route show | grep '^default .* dev {iface}' "
            f"| while read -r line; do sudo ip route del $line; done"
        )
        _ssh_exec(ssh, cleanup_cmd, name)
        Log_Message_To_Custom_File(f"{name}: Deleted default route(s) via {iface}")

        Log_Message_To_Custom_File(f"--- END Cleanup_RPi_Default_Route for {name} ---")
        results[name] = "Routes cleaned"

    return results
   