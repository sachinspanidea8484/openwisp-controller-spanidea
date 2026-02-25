# START_DESCRIPTION

# 1. Initialize logging + SSH connections (DUT + 2 PCs).
# 2. Configure WLAN interfaces & get IPs on both the PCs dynamically.
# 3. Configure Wi-Fi on DUT.
# 4. Baseline connectivity check via ping & collect the latency.
# 5. Run iperf3 server on PC1 & PC2
# 6. Print baseline stats on DUT (CPU, memory used, interrupts).
# 7. Run iperf3 client on PC1 & PC2.
# 8. Keep printing baseline stats on DUT while test is running(CPU, memory used, interrupts)
# 9. Collect logs/results
# 10. Print baseline stats on DUT after test completion(CPU, memory used, interrupts).
# 11. Clean shutdown (stop iperf, close SSH connections, upload logs to server)

# END_DESCRIPTION

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



def main():
	log_message("run start")
