# START_DESCRIPTION

#1.Initialize logging + SSH connections (DUT + 2 PCs). 

#2.Configure Dynamic IP on the PC1 & PC2 Ethernet interface. 

#3.Verify the Ping check From the PC1 ↔ PC2 (DYNAMIC ip). 

#4.Capture baseline CPU, memory, and interrupt statistics from DUT. 

#5.Launch iperf3 servers on PCs and execute bidirectional traffic at 450Mbps for PC1↔PC2, PC2↔PC1. 

#6.Start continuous monitoring of DUT resources (CPU, memory, interrupts) while during iperf. 

#7.Collect post-test CPU, memory, and interrupt statistics from DUT and fetch iperf3 server logs. 

#8.repeat step 3. 

#9..Cleanly shut down by terminating iperf3 sessions, stopping monitoring, closing SSH connections, and upload the logs to the server.

# END_DESCRIPTION


from robot.api.deco import keyword
from robot.libraries.BuiltIn import BuiltIn

from execution.executor_helper import get_registered_executor

from execution.common_helper import (
    log_message,
    fetch_and_validate_rpi_interface_ips,
    ensure_iperf3_on_all_pcs,
    set_ephemeral_port_range,
    set_iperf_port_range,
    allocate_iperf_port,
    start_iperf_server,
    start_iperf_servers_dynamic,
    run_full_mesh_iperf_dynamic,
    monitor_system_stats_around_iperf,
    wait_for_monitoring_to_finish,
    ping_all_devices_using_interface,
    wait_for_all_iperf_clients,
    capture_ifconfig_snapshot_for_devices,
    validate_ifconfig_errors_for_devices,
)

# ---------------- BUILD STATIC IP MAP ----------------
@keyword("Build Static IP Map")
def build_static_ip_map(pc_list, interface=None):
    # Create empty dictionary to store mapping: {device_name: static_ip}
    static_ip_map = {}

    # Log step start (custom logging function from common_helper)
    log_message("[STEP] Building STATIC_IP map")

    # Loop through each PC/device dictionary in the provided list
    for pc in pc_list:

        # Extract device name (e.g., RPI1, RPI2, PC1)
        name = pc["name"]

        # Decide which IP key to use
        # If interface is provided (e.g., "wlan0"), use "wlan0_ip"
        # Otherwise default to "eth1_ip"
        ip_key = f"{interface}_ip" if interface else "eth1_ip"

        # Validate that the required IP key exists in device dictionary
        # If not present, immediately fail the Robot test
        if ip_key not in pc:
            BuiltIn().fail(f"[FAIL] Missing static IP '{ip_key}' for {name}")

        # Add entry to static_ip_map dictionary
        # Example: {"RPI1": "192.168.1.101"}
        static_ip_map[name] = pc[ip_key]

        # Log the mapping for visibility in test logs
        log_message(f"[MAP] {name} -> {pc[ip_key]}")

    # Store this dictionary as a Robot Framework suite variable
    # This allows access across all test cases in the suite
    BuiltIn().set_suite_variable("${STATIC_IP}", static_ip_map)

    # Return the dictionary so it can also be captured in Robot if needed
    return static_ip_map


# ---------------- APPLY STATIC IP ----------------
@keyword("Configure Static IP Temporarily")
def configure_static_ip(pc_list, interface, static_ip_map):

    for pc in pc_list:
        name = pc["name"]
        executor = get_registered_executor(name)

        if name not in static_ip_map:
            BuiltIn().fail(f"[FAIL] No static IP for {name}")

        static_ip = static_ip_map[name]

        log_message(f"[STEP] Applying static IP on {name}:{interface}")

        cmds = [
            f"sudo ip addr flush dev {interface} scope global",
            f"sudo ip addr add {static_ip} dev {interface}",
            f"sudo ip link set {interface} up"
        ]

        for cmd in cmds:
            log_message(f"[CMD] {name}: {cmd}")
            result = executor.execute(cmd)

            if result.stderr:
                BuiltIn().fail(result.stderr)

        log_message(f"[SUCCESS] {name} static IP = {static_ip}", "SUCCESS")

# ---------------- ENABLE DHCP ----------------
@keyword("Enable DHCP On Interface")
def enable_dhcp_on_interface(pc_list, interface):
    """
    Flush static IP and re-enable DHCP on given interface.
    """

    for pc in pc_list:
        name = pc["name"]
        executor = get_registered_executor(name)

        log_message(f"[STEP] Enabling DHCP on {name}:{interface}")

        cmds = [
            f"sudo ip addr flush dev {interface} scope global",    #Removes all global IP addresses from that interface.
            f"sudo dhclient -r {interface}",     # Sends a DHCPRELEASE message to the DHCP server.
            f"sudo dhclient {interface}"              #Requests a new IP from DHCP server.
        ]

        for cmd in cmds:
            log_message(f"[CMD] {name}: {cmd}")
            result = executor.execute(cmd)

            if result.stderr.strip():
                log_message(result.stderr.strip(), "WARN")

        # Verify DHCP IP
        check_cmd = (
            f"ip -4 addr show {interface} | "
            "awk '/inet / {print $2}' | head -n1"
        )

        new_ip = executor.execute(check_cmd).stdout.strip()

        if new_ip:
            log_message(f"[SUCCESS] {name} DHCP IP = {new_ip}", "SUCCESS")
        else:
            log_message(f"[WARN] {name} did not obtain DHCP IP", "WARN")



#
# # ---------------- SAVE ORIGINAL IPs ----------------
# @keyword("Save Original IPs")
# def save_original_ips(pc_list, interface):
#     original_ips = {}
#
#     for pc in pc_list:
#         name = pc["name"]
#         executor = get_registered_executor(name)
#         key = f"{name}_{interface}"
#
#         cmd = (
#             f"ip -4 addr show {interface} | "
#             "awk '/inet / {print $2}' | head -n1"
#         )
#
#         result = executor.execute(cmd)
#         ip = result.stdout.strip()
#
#         if ip:
#             original_ips[key] = ip
#             log_message(f"[SAVE] {key} -> {ip}")
#         else:
#             log_message(f"[WARN] No IP found on {name}:{interface}")
#
#     BuiltIn().set_suite_variable("${ORIGINAL_IPS}", original_ips)
#     return original_ips
#
#
# # ---------------- BUILD STATIC IP MAP ----------------
# @keyword("Build Static IP Map")
# def build_static_ip_map(pc_list, interface=None):
#     static_ip_map = {}
#     log_message("[STEP] Building STATIC_IP map")
#
#     for pc in pc_list:
#         name = pc["name"]
#         ip_key = f"{interface}_ip" if interface else "eth1_ip"
#
#         if ip_key not in pc:
#             BuiltIn().fail(f"[FAIL] Missing static IP '{ip_key}' for {name}")
#
#         static_ip_map[name] = pc[ip_key]
#         log_message(f"[MAP] {name} -> {pc[ip_key]}")
#
#     BuiltIn().set_suite_variable("${STATIC_IP}", static_ip_map)
#     return static_ip_map
#
#
# # ---------------- APPLY STATIC IP ----------------
# @keyword("Configure Static IP Temporarily")
# def configure_static_ip(pc_list, interface, static_ip_map):
#
#     for pc in pc_list:
#         name = pc["name"]
#         executor = get_registered_executor(name)
#
#         if name not in static_ip_map:
#             BuiltIn().fail(f"[FAIL] No static IP for {name}")
#
#         static_ip = static_ip_map[name]
#
#         log_message(f"[STEP] Applying static IP on {name}:{interface}")
#
#         cmds = [
#             f"sudo ip addr flush dev {interface} scope global",
#             f"sudo ip addr add {static_ip} dev {interface}",
#             f"sudo ip link set {interface} up"
#         ]
#
#         for cmd in cmds:
#             log_message(f"[CMD] {name}: {cmd}")
#             result = executor.execute(cmd)
#
#             if result.stderr:
#                 BuiltIn().fail(result.stderr)
#
#         log_message(f"[SUCCESS] {name} static IP = {static_ip}", "SUCCESS")
#
#
# # ---------------- RESTORE ORIGINAL IP ----------------
# @keyword("Restore Original IP")
# def restore_original_ip(pc_list, interface, original_ips):
#
#     if isinstance(original_ips, str):
#         try:
#             original_ips = eval(original_ips)
#         except:
#             original_ips = {}
#
#     for pc in pc_list:
#         name = pc["name"]
#         executor = get_registered_executor(name)
#         key = f"{name}_{interface}"
#
#         log_message(f"[STEP] Restoring IP on {name}:{interface}")
#
#         # ---- Restore Saved IP ----
#         if key in original_ips:
#             orig_ip = original_ips[key]
#
#             cmds = [
#                 f"sudo ip addr flush dev {interface} scope global",
#                 f"sudo ip addr add {orig_ip} dev {interface}",
#                 f"sudo ip link set {interface} up"
#             ]
#
#             for cmd in cmds:
#                 log_message(f"[CMD] {name}: {cmd}")
#                 result = executor.execute(cmd)
#
#                 if result.stderr:
#                     BuiltIn().fail(result.stderr)
#
#             check_cmd = (
#                 f"ip -4 addr show {interface} | "
#                 "awk '/inet / {print $2}' | head -n1"
#             )
#
#             restored = executor.execute(check_cmd).stdout.strip()
#             log_message(f"[VERIFY] {name} restored IP = {restored}")
#
#             log_message(f"[SUCCESS] Restored {name} -> {orig_ip}", "SUCCESS")
#
#         # ---- DHCP FALLBACK ----
#         else:
#             log_message(f"[INFO] No saved IP → DHCP on {name}")
#
#             cmds = [
#                 f"dhclient -r {interface} || true",
#                 f"dhclient {interface} || true"
#             ]
#
#             for cmd in cmds:
#                 executor.execute(cmd)
#
#             log_message(f"[INFO] DHCP enabled on {name}:{interface}")
#
#