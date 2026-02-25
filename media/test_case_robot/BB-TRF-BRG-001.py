# START_DESCRIPTION

# Initialize logging  and establishing SSH connections to DUT and 2 PCs.
# Detect active Ethernet interface on PCs and verify connectivity with pings between 2 PC’s and BB.
# Run idle pings among PCs to establish baseline latency.
# Capture baseline CPU, memory, and interrupt statistics from DUT.
# Start continuous monitoring of DUT resources (CPU, memory, interrupts).
# Launch iperf3 servers on PCs and execute bidirectional traffic at 450 Mbps for PC1↔PC2, PC2↔PC1.
# Collect post-test CPU, memory, and interrupt statistics from DUT and fetch iperf3 server logs.
# Cleanly shut down by terminating iperf3 sessions, stopping monitoring, closing SSH connections, and upload the logs to the server.

# END_DESCRIPTION

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



def main():
	log_message("run start")
