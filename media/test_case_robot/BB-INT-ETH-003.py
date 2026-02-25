import time
import threading
from robot.api.deco import keyword

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

@keyword("Run Directed Iperf Tests PC ↔ BB")
def run_directed_iperf_tests(pc_list, bb, duration, bandwidth, interface):

    bb_exec = get_registered_executor(bb["name"])

    #  Get interface IP map (DO NOT overwrite pc_list)
    rpi_ip_map = fetch_and_validate_rpi_interface_ips(pc_list, interface)

    bb_exec.execute("pkill -f 'iperf3 -s' || true")

    bb_port = allocate_iperf_port()
    bb_exec.execute(
        f"nohup iperf3 -s -p {bb_port} > /tmp/iperf3_bb_{bb_port}.log 2>&1 &"
    )
    log_message(f"BB iperf3 server running on port {bb_port}")
    time.sleep(3)

    for pc in pc_list:

        pc_exec = get_registered_executor(pc["name"])

        #  Get correct wlan0 IP
        pc_ip = rpi_ip_map[pc["name"]]

        bb_ip = bb["ip"]

        log_message(f"{pc['name']} using interface IP {pc_ip}")

        monitor_system_stats_around_iperf(bb, duration)

        _iperf_client(pc_exec, bb_ip, bb_port, duration, bandwidth, pc_ip, udp=True)
        _iperf_client(pc_exec, bb_ip, bb_port, duration, bandwidth, pc_ip, udp=False)

        _iperf_reverse(bb_exec, pc_exec, pc_ip, duration, bandwidth, udp=True)
        _iperf_reverse(bb_exec, pc_exec, pc_ip, duration, bandwidth, udp=False)

        _iperf_bidirectional(pc_exec, bb_exec, pc_ip, bb_ip, duration, bandwidth)

        wait_for_monitoring_to_finish()

def _iperf_client(exec_obj, server_ip, port, duration, bandwidth, bind_ip, udp=False):

    if udp:
        cmd = (
            f"iperf3 -c {server_ip} -p {port} "
            f"-t {duration} -u -b {bandwidth} -B {bind_ip}"
        )
    else:
        cmd = (
            f"iperf3 -c {server_ip} -p {port} "
            f"-t {duration} -B {bind_ip}"
        )

    log_message(f"[IPERF CMD] {cmd}")
    exec_obj.execute(cmd)


# ---------------- IPERF REVERSE (Updated) ---------------- #
def _iperf_reverse(bb_exec, pc_exec, pc_ip, duration, bandwidth, udp=False):
    # Kill old iperf server on PC
    pc_exec.execute("pkill -f 'iperf3 -s' || true")
    pc_port = allocate_iperf_port()
    pc_exec.execute(f"nohup iperf3 -s -p {pc_port} > /tmp/iperf3_pc_{pc_port}.log 2>&1 &")
    log_message(f" PC iperf3 server running on {pc_ip}:{pc_port}")
    time.sleep(3)

    cmd = f"iperf3 -c {pc_ip} -p {pc_port} -t {duration} -P 5"
    if udp:
        cmd += f" -u -b {bandwidth}"

    log_message(f"[IPERF] REVERSE CMD: {cmd}")
    result = bb_exec.execute(cmd)
    if result.stdout:
        log_message(result.stdout)
    if result.stderr:
        log_message(result.stderr, "WARN")



def _start_local_iperf_server(executor, port, tag):
    executor.execute("pkill -f 'iperf3 -s' || true")
    executor.execute(f"nohup iperf3 -s -p {port} > /tmp/iperf3_{tag}_{port}.log 2>&1 &")
    log_message(f"[IPERF] {tag} server started on port {port}")
    time.sleep(2)



def _iperf_bidirectional(pc_exec, bb_exec, pc_ip, bb_ip, duration, bandwidth):
    log_message("[IPERF] BIDIRECTIONAL TCP")
    pc_port = allocate_iperf_port()
    bb_port = allocate_iperf_port()

    # Start servers locally (DO NOT touch common_helper)
    _start_local_iperf_server(pc_exec, pc_port, "PC")
    _start_local_iperf_server(bb_exec, bb_port, "BB")

    t1 = threading.Thread(
        target=_iperf_client,
        args=(pc_exec, bb_ip, bb_port, duration, bandwidth, pc_ip, False)
    )

    t2 = threading.Thread(
        target=_iperf_client,
        args=(bb_exec, pc_ip, pc_port, duration, bandwidth, bb_ip, False)
    )

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    log_message(" Bidirectional TCP test completed")

