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
