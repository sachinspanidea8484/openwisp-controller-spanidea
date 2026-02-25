# START_DESCRIPTION 
# 1. Configure VxLAN tunnel on the Black Box with remote endpoint IP and local interface IP.
# 2. Establish the VxLAN tunnel from Black Box to remote VxLAN endpoint.
# 3. Verify tunnel status on both Black Box and remote endpoint.                                                                                          
# 4. Ping from PC (local) to PC (remote) to verify connectivity
# 5. Verify the encapsulation and decapsulation of packets.

# END_DESCRIPTION

import os
import re
import time
import ipaddress
import threading
import traceback
from datetime import datetime
from robot.api.deco import keyword
from robot.libraries.BuiltIn import BuiltIn


from execution.executor_helper import get_registered_executor


# Setup logs directory and filename
LOG_FOLDER = os.path.join(os.path.dirname(__file__), '..', '..', 'logs')
os.makedirs(LOG_FOLDER, exist_ok=True)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE_PATH = os.path.join(LOG_FOLDER, f"custom_log_{timestamp}.log")


# =============================
# Logging Helper
# =============================
def log_message(message: str):
    """Helper to log to console + file with timestamp"""
    timestamped = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"

    # Show in Robot console output
    BuiltIn().log_to_console(timestamped)

    # Write to custom log file
    with open(LOG_FILE_PATH, "a") as log_file:
        log_file.write(timestamped + "\n")

    
@keyword("Initialize Custom Log File")
def initialize_custom_log_file():
    log_message("[STEP] Custom log initialized")


@keyword("Log Message To Custom File")
def log_message_to_custom_file(message: str):
    log_message(message)


# =============================
# SET UP VXLAN TUNNEL
# =============================
@keyword("SET UP VXLAN TUNNEL ON DUT")
def setup_vxlan_tunnel_dut(
    device_name,
    vxlan_name,
    vxlan_id,
    underlay_iface,
    remote_ip,
    overlay_ip,
    dstport
):
    log_message(f"========== START VXLAN SETUP ON {device_name} ==========")
    log_message(f"Target Device: {device_name}")
    log_message(f"Remote:  {remote_ip}")
    log_message(f"Tunnel IP: {overlay_ip}")

    executor = get_registered_executor(device_name)

    try:
        
         
        # STEP 0: UNDERLAY CONNECTIVITY CHECK
        log_message("[STEP 0] Checking underlay connectivity")

        ping_cmd = f"ping -c 3 -W 2 {remote_ip}"
        log_message(f"[CMD] {ping_cmd}")

        ping_res = executor.execute(ping_cmd)
        if ping_res.failed or "0% packet loss" not in ping_res.stdout:
            raise AssertionError(
                f"Underlay connectivity check FAILED\n"
                f"Cannot ping remote underlay IP {remote_ip}\n"
                f"stdout:\n{ping_res.stdout}\n"
                f"stderr:\n{ping_res.stderr}"
            )

        log_message("[OK] Underlay connectivity verified")    
        
        # STEP 1: Cleanup
        log_message("[STEP 1] Cleaning up old VxLAN interface")
        cmds_cleanup = [
                f"ip addr del {overlay_ip} dev {vxlan_name} 2>/dev/null || true",
                f"ip link set {vxlan_name} down 2>/dev/null || true",
                f"ip link delete {vxlan_name} 2>/dev/null || true",
            ]
        for cmd in cmds_cleanup:
            log_message(f"[CMD] {cmd}")
            executor.execute(cmd)

        # STEP 2: Create VXLAN
        log_message("[STEP 2] Creating VXLAN tunnel")
        create_cmd = (
                f"ip link add {vxlan_name} type vxlan id {vxlan_id} "
                f"dev {underlay_iface} remote {remote_ip} dstport {dstport}"
        )
       
        log_message(f"[CMD] {create_cmd}")
        result = executor.execute(create_cmd)

        if result.failed:
                raise AssertionError(
                    f"VxLAN tunnel creation failed on {device_name}\n"
                    f"stdout: {result.stdout}\n"
                    f"stderr: {result.stderr}"
                )

            # STEP 3: Bring interface up
        log_message("[STEP 3] Bringing VxLAN interface UP")
        result = executor.execute(f"ip link set {vxlan_name} up")

        if result.failed:
                raise AssertionError(
                    f"Failed to bring VxLAN interface {vxlan_name} UP on {device_name}"
                )
            # STEP 4: Assign overlay IP
        log_message(f"[STEP 4] Assigning IP {overlay_ip} to {vxlan_name}")
        result = executor.execute(
                f"ip addr add {overlay_ip}/24 dev {vxlan_name}"
            )

        if result.failed:
                raise AssertionError(
                    f"Failed to assign IP {overlay_ip}/24 to {vxlan_name}"
                )
            
        log_message(f"========== VxLAN SETUP COMPLETE ON {device_name} ==========")
        return 0

    except AssertionError:
        log_message("========== VxLAN SETUP FAILED (ASSERTION) ==========")
        raise

    except Exception as e:
        log_message("========== VxLAN SETUP FAILED (EXCEPTION) ==========")
        raise AssertionError(
            f"Unexpected error during VxLAN setup \n"
            f"{type(e).__name__}: {str(e)}\n"
            f"Traceback:\n{traceback.format_exc()}"
        )


@keyword("SET UP VXLAN TUNNEL ON PC")
def setup_vxlan_tunnel_pc(
    device_name,
    pc_pass,
    vxlan_name,
    vxlan_id,
    underlay_iface,
    remote_ip,
    overlay_ip,
    dstport
):
    log_message(f"========== START VXLAN SETUP ON {device_name} ==========")
    log_message(f"Target Device: {device_name}")
    log_message(f"Remote:  {remote_ip}")
    log_message(f"Tunnel IP: {overlay_ip}")
    
    def sudo(cmd):
        log_message(f"[CMD] sudo **** | {cmd}")
        return f"echo '{pc_pass}' | sudo -S {cmd}"

    executor = get_registered_executor(device_name)

    try:
         
        # STEP 0: UNDERLAY CONNECTIVITY CHECK
        log_message("[STEP 0] Checking underlay connectivity")

        ping_cmd = f"ping -c 3 -W 2 {remote_ip}"
        log_message(f"[CMD] {ping_cmd}")

        ping_res = executor.execute(ping_cmd)
        if ping_res.failed or "0% packet loss" not in ping_res.stdout:
            raise AssertionError(
                f"Underlay connectivity check FAILED\n"
                f"Cannot ping remote underlay IP {remote_ip}\n"
                f"stdout:\n{ping_res.stdout}\n"
                f"stderr:\n{ping_res.stderr}"
            )

        log_message("[OK] Underlay connectivity verified")    
        
        # STEP 1: Cleanup
        log_message("[STEP 1] Cleaning up old VxLAN interface")
        cmds_cleanup = [
                f"ip addr del {overlay_ip} dev {vxlan_name} 2>/dev/null || true",
                f"ip link set {vxlan_name} down 2>/dev/null || true",
                f"ip link delete {vxlan_name} 2>/dev/null || true",
            ]
        for cmd in cmds_cleanup:
            # log_message(f"[CMD] {cmd}")
            executor.execute(sudo(cmd))

        # STEP 2: Create VXLAN
        log_message("[STEP 2] Creating VXLAN tunnel")
        create_cmd = (
                f"ip link add {vxlan_name} type vxlan id {vxlan_id} "
                f"dev {underlay_iface} remote {remote_ip} dstport {dstport}"
        )
       
        # log_message(f"[CMD] {create_cmd}")
        result = executor.execute(sudo(create_cmd))

        if result.failed:
                raise AssertionError(
                    f"VxLAN tunnel creation failed on {device_name}\n"
                    f"stdout: {result.stdout}\n"
                    f"stderr: {result.stderr}"
                )

            # STEP 3: Bring interface up
        log_message("[STEP 3] Bringing VxLAN interface UP")
        result = executor.execute(sudo(f"ip link set {vxlan_name} up"))

        if result.failed:
                raise AssertionError(
                    f"Failed to bring VxLAN interface {vxlan_name} UP on {device_name}"
                )
            # STEP 4: Assign overlay IP
        log_message(f"[STEP 4] Assigning IP {overlay_ip} to {vxlan_name}")
        result = executor.execute(sudo(
                f"ip addr add {overlay_ip}/24 dev {vxlan_name}"
                 )
            )

        if result.failed:
                raise AssertionError(
                    f"Failed to assign IP {overlay_ip}/24 to {vxlan_name}"
                )
            
        log_message(f"========== VxLAN SETUP COMPLETE ON {device_name} ==========")
        return 0

    except AssertionError:
        log_message("========== VxLAN SETUP FAILED (ASSERTION) ==========")
        raise

    except Exception as e:
        log_message("========== VxLAN SETUP FAILED (EXCEPTION) ==========")
        raise AssertionError(
            f"Unexpected error during VxLAN setup \n"
            f"{type(e).__name__}: {str(e)}\n"
            f"Traceback:\n{traceback.format_exc()}"
        )


        
@keyword("VERIFY VXLAN TUNNEL")
def verify_vxlan_tunnel(
    protocol, capture_node_name, capture_node_pass, ping_node_name,
    capture_node_iface, capture_node_outer_ip, ping_node_outer_ip,
    capture_node_inner_ip, ping_node_inner_ip, vni=100
):
    capture_node_executor = get_registered_executor(capture_node_name)
    ping_node_executor = get_registered_executor(ping_node_name)
    
    log_message("[STEP] Starting VXLAN tunnel verification")
    log_message(f"[INFO] Capture Node : {capture_node_name}")
    log_message(f"[INFO] Ping Node    : {ping_node_name}")
    log_message(f"[INFO] Underlay IF  : {capture_node_iface}")
    log_message(f"[INFO] OUTER IPs    : {capture_node_outer_ip} <-> {ping_node_outer_ip}")
    log_message(f"[INFO] INNER IPs    : {capture_node_inner_ip} <-> {ping_node_inner_ip}")
    log_message(f"[INFO] VNI          : {vni}")

    pcap_file = "/tmp/vxlan_capture.pcap"
    vxlan_port = 4789

    try:
        def sudo(cmd):
            return f"echo '{capture_node_pass}' | sudo -S {cmd}"

        tcpdump_output = {"stdout": "", "stderr": "", "failed": True}
        ping_output = {"stdout": "", "stderr": "", "failed": True}

        os_info = capture_node_executor.execute(
            "cat /etc/os-release 2>/dev/null || true"
        ).stdout.lower()

        is_openwrt = "openwrt" in os_info
        is_mqtt = protocol.upper() == "MQTT"

        # ---------------- PING THREAD ----------------
        def run_ping():
            try:
                time.sleep(2)  # Give tcpdump a moment to start
                cmd = f"ping -c 5 {capture_node_inner_ip}"
                log_message(f"[PING] {cmd}")
                result = ping_node_executor.execute(cmd)
                ping_output.update(stdout=result.stdout, stderr=result.stderr, failed=result.failed)
            except Exception as e:
                ping_output["stderr"] = str(e)
                ping_output["failed"] = True

        # ---------------- TCPDUMP THREAD ----------------
        def run_tcpdump():
            try:
                # VXLAN uses UDP 4789
                filter_cmd = f"udp port {vxlan_port}"
                
                if is_mqtt:
                    log_message("[TCPDUMP] MQTT mode → background capture")
                    capture_node_executor.execute(f"rm -f {pcap_file} 2>/dev/null || true")

                    # Start background capture
                    # cmd_base = f"tcpdump -i {capture_node_iface} -nn {filter_cmd} -w {pcap_file} & echo $!"
                    # cmd_base = f"tcpdump -i any -nn {filter_cmd} -w  {pcap_file} & echo $!"
                    cmd_base =(f"tcpdump -i any -nn -U -c 10 {filter_cmd} -w {pcap_file} > /dev/null 2>&1 & echo $!")
                    start_cmd = cmd_base if is_openwrt else sudo(cmd_base)
                    
                    pid_result = capture_node_executor.execute(start_cmd)
                    tcpdump_pid = pid_result.stdout.strip()

                    time.sleep(10) # Wait for ping thread to finish

                    capture_node_executor.execute(f"kill -INT {tcpdump_pid} 2>/dev/null || true")
                    read_cmd = f"tcpdump -nn -vv -r {pcap_file}"
                    result = capture_node_executor.execute(read_cmd)
                else:
                    log_message("[TCPDUMP] SSH mode → live capture")
                    # cmd_base = f"tcpdump -i {capture_node_iface} -nn -vv -c 10 {filter_cmd}"
                    cmd_base = f"tcpdump -i any -nn -vv -c 10 {filter_cmd}"
                    cmd = cmd_base if is_openwrt else sudo(cmd_base)
                    result = capture_node_executor.execute(cmd)

                tcpdump_output.update(stdout=result.stdout, stderr=result.stderr, failed=result.failed)
            except Exception as e:
                tcpdump_output["stderr"] = str(e)
                tcpdump_output["failed"] = True
        
        # ---------------- RUN THREADS ----------------
        t1 = threading.Thread(target=run_tcpdump)
        t2 = threading.Thread(target=run_ping)
        t1.start(); t2.start()
        t1.join(); t2.join()
        
        # ---------------- OUTPUT ----------------
        log_message("[OUTPUT] ===== PING =====")
        log_message(ping_output["stdout"])
        log_message("[OUTPUT] ===== TCPDUMP =====")
        log_message(tcpdump_output["stdout"])
   
        # ---------------- VALIDATION ----------------
        if tcpdump_output["failed"]:
            raise AssertionError("tcpdump failed — cannot validate VXLAN")

        tcpdump_lines = tcpdump_output["stdout"].splitlines()

        # ---- VXLAN HEADER & VNI CHECK ----
        vni_hits = [l for l in tcpdump_lines if f"vni {vni}" in l.lower()]
        if not vni_hits:
            raise AssertionError(f"VXLAN VNI {vni} not detected in traffic")
        
        log_message(f"[OK] VXLAN header and VNI {vni} detected")
        # Log the first match found for verification
        log_message(f"    [MATCH] {vni_hits[0].strip()}")

        # ---- OUTER IP CHECK ----
        # Looking for Outer IP flow: Ping Node -> Capture Node on Port 4789
        outer_fwd_hits = [l for l in tcpdump_lines if ping_node_outer_ip in l and f"{capture_node_outer_ip}.{vxlan_port}" in l]
        
        if not outer_fwd_hits:
             raise AssertionError("OUTER forward VXLAN traffic (UDP 4789) missing")
        
        log_message("[OK] VXLAN forward OUTER encapsulation detected")
        # Log the first match found for verification
        log_message(f"    [MATCH] {outer_fwd_hits[0].strip()}")

        # ---- INNER ICMP CHECK ----
        inner_forward = f"{ping_node_inner_ip} > {capture_node_inner_ip}: ICMP"
        inner_hits = [l for l in tcpdump_lines if inner_forward in l]
        
        if inner_hits:
            log_message("[OK] INNER ICMP traffic observed inside VXLAN")
            log_message(f"    [MATCH] {inner_hits[0].strip()}")
        else:
            log_message("[WARN] INNER ICMP not explicitly decoded (background traffic captured first)")

        # ---- PING RESULT CHECK ----
        if "0% packet loss" not in ping_output["stdout"]:
            raise AssertionError(f"Ping failed or packet loss detected: {ping_output['stdout']}")

        log_message("[SUCCESS] VXLAN tunnel verification PASSED")
        return True

    finally:
        capture_node_executor.execute(f"rm -f {pcap_file} 2>/dev/null || true")


# =============================
# TEARDOWN VXLAN TUNNEL
# =============================
@keyword("TEARDOWN VXLAN TUNNEL")
def teardown_vxlan_tunnel(device_name,device_pass,tunnel_name):
    log_message(f"Target Device: {device_name}")
    log_message(f"VXLAN Interface: {tunnel_name}")
    
    def sudo(cmd):
        log_message(f"[CMD] sudo **** | {cmd}")
        return f"echo '{device_pass}' | sudo -S {cmd}"
    
    executor = get_registered_executor(device_name)
    try:
        
        log_message("[STEP 1] Removing VXLAN interface")
        
        cmds = [
            f"ip link set {tunnel_name} down || true",
            f"ip link delete {tunnel_name} || true"
        ]
            # Detect OS
        os_info = executor.execute("cat /etc/os-release 2>/dev/null || true").stdout.lower()
        for cmd in cmds:
            if "openwrt" in os_info:
                    log_message(f"[CMD] {cmd}")
                    result = executor.execute(cmd)
            else:   
                    result = executor.execute(sudo(cmd))
        if result.failed:
                raise AssertionError(
                    f"VXLAN tunnel teardown failed on {device_name}\n"
                    f"stdout: {result.stdout}\n"
                    f"stderr: {result.stderr}"
                )
        log_message("VXLANinterface removed")
        return True

    except Exception as e:
        log_message("VXLAN teardown failed due to exception")
        log_message(str(e))
        log_message(traceback.format_exc())
        return False
   