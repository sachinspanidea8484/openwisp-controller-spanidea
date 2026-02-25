# START_DESCRIPTION

#1.Initialize logging + SSH connections (DUT + 2 PCs). 
# 2. Start idle network ping to establish baseline values for CPU load and memory usage values 
# 3.Start logging of CPU load, memory usage, OS interrupt data 
# 4.For each of the 2 GbE interfaces, execute iperf3 (each test for each port for 2 min) 

#     a.450 MBPS unidirectional PC → BB UDP 

#     b.450 MBPS unidirectional PC → BB TCP 

#     c.450 Mbps unidirectional BB → PC UDP 

#     d.450 Mbps unidirectional BB → PC TCP 

#     e.450 Mbps bidirectional each direction PC ↔ BB TCP 
    
# 5. Start continuous monitoring of DUT resources (CPU, memory, interrupts) while during iperf. 
# 6. Collect post-test CPU, memory, and interrupt statistics from DUT and fetch iperf3 server logs. 
# 7. repeat step2
# 8. Cleanly shut down by terminating iperf3 sessions, stopping monitoring, closing SSH connections, and upload the logs to the server.

# END_DESCRIPTION


import re
import time
import threading
import traceback
from robot.api.deco import keyword

from execution.executor_helper import get_registered_executor

from execution.common_helper import (
    log_message,
    fetch_and_validate_rpi_interface_ips,
    ensure_iperf3_on_all_pcs,
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


# ------------------ WiFi Configuration ----------------
def configure_openwrt_wireless(device, ssid, password, encryption="psk2"):
    device_name = device["name"]
    executor = get_registered_executor(device_name)
    try:
        result = executor.execute(f"uci show wireless | grep \".ssid='{ssid}'\"")
        output = result.stdout or ""
        log_message(f"uci show result:\n{output}")
        if output.strip():
            log_message(f"SSID '{ssid}' already exists. Updating settings...")
            matches = re.findall(r"(wireless\.(?:@wifi-iface\[\d+\]|wifinet\d+))\.ssid", output)
            iface_index = matches[0] if matches else None
            if iface_index:
                cmds = [
                    f"uci set {iface_index}.mode='ap'",
                    f"uci set {iface_index}.ssid='{ssid}'",
                    f"uci set {iface_index}.encryption='{encryption}'",
                    f"uci set {iface_index}.key='{password}'",
                    f"uci set {iface_index}.network='lan'",
                    f"uci set {iface_index}.disabled='0'",
                ]
                for cmd in cmds:
                    log_message(f"[CMD] {cmd}")
                    result = executor.execute(cmd)
                    log_message(f"[OUT]\n{result.stdout}")
                    if result.stderr:
                        log_message(f"[ERR]\n{result.stderr}")
                log_message("[CMD] uci commit wireless && wifi reload")
                result = executor.execute("uci commit wireless && wifi reload")
                log_message(f"[OUT]\n{result.stdout}")
                log_message(f"SSID '{ssid}' updated successfully.")
                return True
        # Create new AP
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
            result = executor.execute(cmd)
            log_message(f"[OUT]\n{result.stdout}")
            if result.stderr:
                log_message(f"[ERR]\n{result.stderr}")
        log_message(f"SSID '{ssid}' created and enabled successfully.")
        return True
    except Exception as e:
        log_message(f"WIFI SETUP failed: {e}", "ERROR")
        traceback.print_exc()
        raise


def configure_rpi_wifi(pc, ssid, psk):
    pc_name = pc["name"]
    executor = get_registered_executor(pc_name)
    log_message(f"Configuring RPi WiFi on {pc_name}")
    wpa_conf = f"""ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

network={{
    ssid="{ssid}"
    psk="{psk}"
    key_mgmt=WPA-PSK
}}
"""
    cmd = f"""sudo bash -c 'cat << "EOF" > /etc/wpa_supplicant/wpa_supplicant.conf
{wpa_conf}
EOF'"""
    log_message("[CMD] Write wpa_supplicant.conf")
    executor.execute(cmd)
    cmds = [
        "sudo pkill wpa_supplicant || true",
        "sudo ip link set wlan0 down",
        "sudo ip link set wlan0 up",
        "sudo wpa_supplicant -B -i wlan0 -c /etc/wpa_supplicant/wpa_supplicant.conf >/dev/null 2>&1",
    ]
    for cmd in cmds:
        log_message(f"[CMD] {cmd}")
        executor.execute(cmd)
        time.sleep(1)
    # DHCP retry
    for attempt in range(1, 6):
        log_message(f" DHCP retry {attempt}/5 for {pc_name}")
        executor.execute("sudo dhclient -r wlan0 || true")
        executor.execute("sudo dhclient wlan0")
        time.sleep(1)
        result = executor.execute("ip -4 addr show wlan0 | grep -oP '(?<=inet\\s)\\d+(\\.\\d+){3}'")
        dhcp_ip = (result.stdout or "").strip()
        if dhcp_ip:
            log_message(f"{pc_name} got IP {dhcp_ip}")
            return dhcp_ip
    raise RuntimeError(f"{pc_name} failed to get DHCP IP")


@keyword("Configure Devices Parallel")
def configure_devices_parallel(dut, pcs, ssid, psk2):
    log_message(" Starting parallel WiFi configuration")
    threads = []
    t = threading.Thread(target=_safe_configure_openwrt, args=(dut, ssid, psk2))
    threads.append(t)
    for pc in pcs:
        t = threading.Thread(target=_safe_configure_rpi, args=(pc, ssid, psk2))
        threads.append(t)
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    log_message("Parallel WiFi configuration completed")


def _safe_configure_openwrt(dut, ssid, psk):
    try:
        configure_openwrt_wireless(dut, ssid, psk)
    except Exception as e:
        log_message(f"OpenWrt WiFi config failed: {e}", "ERROR")
        traceback.print_exc()
        raise


def _safe_configure_rpi(pc, ssid, psk):
    try:
        configure_rpi_wifi(pc, ssid, psk)
    except Exception as e:
        log_message(f"RPi WiFi config failed on {pc['name']}: {e}", "ERROR")
        traceback.print_exc()
        raise

@keyword("Run Full Mesh All Protocols")
def run_full_mesh_all_protocols(pc_list, nokia, duration, bandwidth, protocol_list, interface="none"):

    if isinstance(protocol_list, str):
        protocol_list = [protocol_list]

    log_message(f"[IPERF] Protocol list = {protocol_list}")

    ensure_iperf3_on_all_pcs(pc_list)

    for proto in protocol_list:
        proto = proto.upper()
        log_message(f"Running full-mesh {proto} iperf3 test")

        # Start servers
        start_iperf_servers_dynamic(pc_list)

        # Start monitoring
        monitor_system_stats_around_iperf(nokia, duration)

        # Run traffic
        run_full_mesh_iperf_dynamic(
            pc_list,
            duration,
            bandwidth,
            interface=interface,
            protocol=proto
        )

        wait_for_all_iperf_clients()
        wait_for_monitoring_to_finish()

        log_message(f"Completed {proto} test")

