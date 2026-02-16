import time
import threading
from robot.libraries.BuiltIn import BuiltIn
from robot.api.deco import keyword

# ---------------- LOGGING ---------------- #
@keyword
def log_message_to_custom_file(msg):
    """Logs message to Robot log and console."""
    BuiltIn().log(msg)
    BuiltIn().log_to_console(msg)

# ---------------- WLAN DETECTION ---------------- #
@keyword
def get_wlan0_interface_and_ip(alias):
    """Detects WLAN interface and its IP on the given device alias."""
    ssh_lib = BuiltIn().get_library_instance("SSHLibrary")
    ssh_lib.switch_connection(alias)
    cmd = "ip -4 -o addr show | grep -E 'wl|wlan' | awk '{print $2, $4}' | cut -d/ -f1 | head -n1"
    result = ssh_lib.execute_command(cmd).strip()
    if not result:
        log_message_to_custom_file(f"❌ No WLAN interface found on {alias}")
        return '', ''
    iface, ip = result.split()
    log_message_to_custom_file(f"✅ Found interface {iface} with IP {ip} on {alias}")
    return iface, ip

# ---------------- PING ---------------- #
@keyword
def run_ping(alias, target_ip, count=4):
    """Runs ping from alias to target IP and logs output."""
    ssh_lib = BuiltIn().get_library_instance("SSHLibrary")
    ssh_lib.switch_connection(alias)
    cmd = f"ping -c {count} {target_ip}"
    result = ssh_lib.execute_command(cmd)
    log_message_to_custom_file(f"Ping from {alias} to {target_ip}:\n{result}")
    return result

# ---------------- IPERF ---------------- #
@keyword
def run_iperf_server(alias):
    """Starts iperf3 server in background and logs server PID."""
    ssh_lib = BuiltIn().get_library_instance("SSHLibrary")
    ssh_lib.switch_connection(alias)
    cmd = "nohup iperf3 -s -1 > /tmp/iperf3_server.log 2>&1 & echo $!"
    pid = ssh_lib.execute_command(cmd).strip()
    log_message_to_custom_file(f"Started iperf3 server on {alias} with PID {pid}")
    return pid

@keyword
def run_iperf_client(client_alias, server_ip, bind_ip, duration, bandwidth):
    """Runs iperf3 client from client_alias to server_ip and logs output."""
    ssh_lib = BuiltIn().get_library_instance("SSHLibrary")
    ssh_lib.switch_connection(client_alias)
    cmd = f"iperf3 -c {server_ip} -B {bind_ip} -t {duration} -b {bandwidth}"
    log_message_to_custom_file(f"Starting iperf3 client on {client_alias}:\n{cmd}")
    result = ssh_lib.execute_command(cmd)
    log_message_to_custom_file(f"Iperf3 client output on {client_alias}:\n{result}")
    return result

@keyword
def fetch_iperf_server_log(alias):
    """Fetches the iperf3 server output log and logs it to Robot log."""
    ssh_lib = BuiltIn().get_library_instance("SSHLibrary")
    ssh_lib.switch_connection(alias)
    log_content = ssh_lib.execute_command("cat /tmp/iperf3_server.log")
    log_message_to_custom_file(f"Iperf3 server log from {alias}:\n{log_content}")
    return log_content

# ---------------- WIFI CONFIG ---------------- #
@keyword
def configure_wifi(pc_list):
    """Dummy WiFi configuration placeholder."""
    for pc in pc_list:
        log_message_to_custom_file(f"🔎 Configuring WiFi on {pc}")
    return pc_list

# ---------------- Monitoring ---------------- #
# ---------------- RESOURCE MONITORING ---------------- #
def monitor_resources_thread(alias, duration):
    """Monitor CPU, memory, and interrupts on the BB device."""
    ssh_lib = BuiltIn().get_library_instance("SSHLibrary")
    ssh_lib.switch_connection(alias)

    log_message_to_custom_file(f"📊 Starting resource monitoring on {alias} for {duration}s")

    # Before test
    log_message_to_custom_file("📊 BB Stats BEFORE")
    cpu = ssh_lib.execute_command("cat /proc/stat | head -n5")
    mem = ssh_lib.execute_command("cat /proc/meminfo | head -n3")
    irq = ssh_lib.execute_command("head -n5 /proc/interrupts")
    log_message_to_custom_file(f"[{alias} BEFORE] CPU: {cpu.strip()} | MEM: {mem.strip()} | IRQ: {irq.strip()}")

    # During test
    log_message_to_custom_file("📊 BB Stats DURING")
    start_time = time.time()
    while time.time() - start_time < duration:
        cpu = ssh_lib.execute_command("cat /proc/stat | head -n5")
        mem = ssh_lib.execute_command("cat /proc/meminfo | head -n3")
        irq = ssh_lib.execute_command("head -n5 /proc/interrupts")
        log_message_to_custom_file(f"[{alias} DURING] CPU: {cpu.strip()} | MEM: {mem.strip()} | IRQ: {irq.strip()}")
        time.sleep(1)

    # After test
    log_message_to_custom_file("📊 BB Stats AFTER")
    cpu = ssh_lib.execute_command("cat /proc/stat | head -n5")
    mem = ssh_lib.execute_command("cat /proc/meminfo | head -n3")
    irq = ssh_lib.execute_command("head -n5 /proc/interrupts")
    log_message_to_custom_file(f"[{alias} AFTER] CPU: {cpu.strip()} | MEM: {mem.strip()} | IRQ: {irq.strip()}")

@keyword
def start_monitoring_in_thread(alias, duration):
    """Starts resource monitoring in a separate thread and returns the thread object."""
    thread = threading.Thread(target=monitor_resources_thread, args=(alias, duration))
    thread.start()
    return thread

@keyword
def wait_for_thread_to_finish(thread):
    """Joins the monitoring thread."""
    thread.join()
