# START_DESCRIPTION
# 1. Configure L2TP tunnel on the Black Box with remote endpoint IP and local interface IP.
# 2. Establish the L2TP tunnel from Black Box to remote L2TP endpoint.
# 3. Verify tunnel status on both Black Box and remote endpoint.                                                                                          
# 4. Ping from PC (local) to PC (remote) to verify connectivity
# 5. Verify the encapsulation and decapsulation of packets.
# END_DESCRIPTION

import os
import time
import threading
import traceback
from datetime import datetime
from robot.api.deco import keyword
from robot.libraries.BuiltIn import BuiltIn


# from execution.connection_manager import get_executor
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
# SET UP L2TP TUNNEL
# =============================
@keyword("SET UP L2TP TUNNEL ON DUT")
def setup_l2tp_tunnel_dut(
    device_name,
    local_ip, remote_ip,
    tunnel_id, session_id,
    peer_tunnel_id, peer_session_id,
    overlay_ip, udp_port
):
    log_message("========== START L2TP SETUP ==========")
    log_message(f"Device             : {device_name}")
    log_message(f"Local IP           : {local_ip}")
    log_message(f"Remote IP          : {remote_ip}")
    log_message(f"L2TP Tunnel        : {tunnel_id} <-> {peer_tunnel_id}")
    log_message(f"L2TP Session       : {session_id} <-> {peer_session_id}")
    log_message(f"L2TP Interface IP  : {overlay_ip}")
    log_message(f"UDP Port           : {udp_port}")
    
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
            
            log_message("[STEP 1] Cleaning existing L2TP session/tunnel")
            executor.execute(f"ip l2tp del session tunnel_id {tunnel_id} session_id {session_id} 2>/dev/null || true")
            executor.execute(f"ip l2tp del tunnel tunnel_id {tunnel_id} 2>/dev/null || true")
            time.sleep(1)
            log_message("[OK] Cleanup completed")
            log_message("[STEP 2] Creating L2TP tunnel")

            tunnel_cmd = (
                f"ip l2tp add tunnel "
                f"tunnel_id {tunnel_id} peer_tunnel_id {peer_tunnel_id} "
                f"encap udp local {local_ip} remote {remote_ip} "
                f"udp_sport {udp_port} udp_dport {udp_port}"
            )

            log_message(f"[CMD] {tunnel_cmd}")
            result = executor.execute(tunnel_cmd)

            if result.failed:
                raise AssertionError(
                    f"L2TP tunnel creation failed\n"
                    f"stdout: {result.stdout}\n"
                    f"stderr: {result.stderr}"
                )

            log_message("[OK] L2TP tunnel created")

            log_message("[STEP 3] Creating L2TP session")

            session_cmd = (
                f"ip l2tp add session "
                f"name l2tpeth0 "
                f"tunnel_id {tunnel_id} session_id {session_id} "
                f"peer_session_id {peer_session_id}"
            )

            log_message(f"[CMD] {session_cmd}")
            result = executor.execute(session_cmd)

            if result.failed:
                raise AssertionError(
                    f"L2TP session creation failed\n"
                    f"stdout: {result.stdout}\n"
                    f"stderr: {result.stderr}"
                )

            log_message("[OK] L2TP session created")
            log_message("[STEP 4] Bringing l2tpeth0 UP")
            result = executor.execute("ip link set l2tpeth0 up")

            if result.failed:
                raise AssertionError(
                    f"Failed to bring l2tpeth0 UP\n"
                    f"stderr: {result.stderr}"
                )

            log_message("[OK] l2tpeth0 is UP")
            log_message(f"[STEP 5] Assigning IP {overlay_ip}/24 to l2tpeth0")

            result = executor.execute(f"ip addr add {overlay_ip}/24 dev l2tpeth0")
            if result.failed:
                log_message("[WARN] IP may already exist, flushing and retrying")
                executor.execute("ip addr flush dev l2tpeth0")

                retry = executor.execute(
                    f"ip addr add {overlay_ip}/24 dev l2tpeth0"
                )

                if retry.failed:
                    raise AssertionError(
                        f"Failed to assign IP {overlay_ip}/24 to l2tpeth0\n"
                        f"stderr: {retry.stderr}"
                    )

            log_message("[OK] IP assigned")
            log_message("[VERIFY] Interface status")
            iface_info = executor.execute("ip addr show l2tpeth0")

            if "l2tpeth0" not in iface_info.stdout:
                raise AssertionError("l2tpeth0 interface not found after setup")

            log_message(iface_info.stdout)

            log_message("[VERIFY] L2TP session status")
            sess_info = executor.execute("ip l2tp show session")

            if str(session_id) not in sess_info.stdout:
                raise AssertionError("L2TP session not visible in kernel")

            log_message(sess_info.stdout)

            log_message("========== L2TP SETUP COMPLETE ==========")
            return True

    except AssertionError:
        log_message("========== L2TP SETUP FAILED (ASSERTION) ==========")
        raise

    except Exception as e:
        log_message("========== L2TP SETUP FAILED (EXCEPTION) ==========")
        raise AssertionError(
            f"Unexpected error during L2TP setup on {device_name}\n"
            f"{type(e).__name__}: {str(e)}\n"
            f"Traceback:\n{traceback.format_exc()}"
        )

#=====================RPI========================
@keyword("SET UP L2TP TUNNEL ON RPI")
def setup_l2tp_tunnel_rpi(
    rpi_name, rpi_pass,
    local_ip, remote_ip,
    tunnel_id, session_id,
    peer_tunnel_id, peer_session_id,
    overlay_ip, udp_port
):  
    def sudo(cmd):
        log_message(f"[CMD] sudo **** | {cmd}")
        return f"echo '{rpi_pass}' | sudo -S {cmd}"
    
    log_message("========== START L2TP SETUP ==========")
    log_message(f"Device             : {rpi_name}")
    log_message(f"Local IP           : {local_ip}")
    log_message(f"Remote IP          : {remote_ip}")
    log_message(f"L2TP Tunnel        : {tunnel_id} <-> {peer_tunnel_id}")
    log_message(f"L2TP Session       : {session_id} <-> {peer_session_id}")
    log_message(f"L2TP Interface IP  : {overlay_ip}")
    log_message(f"UDP Port           : {udp_port}")
    
    executor = get_registered_executor(rpi_name)
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
            
            log_message("[STEP 1] Cleaning existing L2TP session/tunnel")
            executor.execute(sudo(f"ip l2tp del session tunnel_id {tunnel_id} session_id {session_id} 2>/dev/null || true"))
            executor.execute(sudo(f"ip l2tp del tunnel tunnel_id {tunnel_id} 2>/dev/null || true"))
            time.sleep(1)
            
            log_message("[OK] Cleanup completed")
            log_message("[STEP 2] Creating L2TP tunnel")
     
            tunnel_cmd = sudo((
                f"ip l2tp add tunnel "
                f"tunnel_id {tunnel_id} peer_tunnel_id {peer_tunnel_id} "
                f"encap udp local {local_ip} remote {remote_ip} "
                f"udp_sport {udp_port} udp_dport {udp_port}"
            ))

            result = executor.execute(tunnel_cmd)

            if result.failed:
                raise AssertionError(
                    f"L2TP tunnel creation failed\n"
                    f"stdout: {result.stdout}\n"
                    f"stderr: {result.stderr}"
                )

            log_message("[OK] L2TP tunnel created")

            log_message("[STEP 3] Creating L2TP session")

            session_cmd = sudo((
                f"ip l2tp add session "
                f"name l2tpeth0 "
                f"tunnel_id {tunnel_id} session_id {session_id} "
                f"peer_session_id {peer_session_id}"
            ))

            result = executor.execute(session_cmd)

            if result.failed:
                raise AssertionError(
                    f"L2TP session creation failed\n"
                    f"stdout: {result.stdout}\n"
                    f"stderr: {result.stderr}"
                )

            log_message("[OK] L2TP session created")
            log_message("[STEP 4] Bringing l2tpeth0 UP")
            result = executor.execute(sudo("ip link set l2tpeth0 up"))

            if result.failed:
                raise AssertionError(
                    f"Failed to bring l2tpeth0 UP\n"
                    f"stderr: {result.stderr}"
                )

            log_message("[OK] l2tpeth0 is UP")
            log_message(f"[STEP 5] Assigning IP {overlay_ip}/24 to l2tpeth0")

            result = executor.execute(sudo(f"ip addr add {overlay_ip}/24 dev l2tpeth0"))
            if result.failed:
                log_message("[WARN] IP may already exist, flushing and retrying")
                executor.execute("ip addr flush dev l2tpeth0")

                retry = executor.execute(sudo(
                    f"ip addr add {overlay_ip}/24 dev l2tpeth0"
                ))

                if retry.failed:
                    raise AssertionError(
                        f"Failed to assign IP {overlay_ip}/24 to l2tpeth0\n"
                        f"stderr: {retry.stderr}"
                    )

            log_message("[OK] IP assigned")
            log_message("[VERIFY] Interface status")
            iface_info = executor.execute("ip addr show l2tpeth0")

            if "l2tpeth0" not in iface_info.stdout:
                raise AssertionError("l2tpeth0 interface not found after setup")

            log_message(iface_info.stdout)

            log_message("[VERIFY] L2TP session status")
            sess_info = executor.execute(sudo("ip l2tp show session"))

            if str(session_id) not in sess_info.stdout:
                raise AssertionError("L2TP session not visible in kernel")

            log_message(sess_info.stdout)

            log_message("========== L2TP SETUP COMPLETE ==========")
            return True

    except AssertionError:
        log_message("========== L2TP SETUP FAILED (ASSERTION) ==========")
        raise

    except Exception as e:
        log_message("========== L2TP SETUP FAILED (EXCEPTION) ==========")
        raise AssertionError(
            f"Unexpected error during L2TP setup on {rpi_name}\n"
            f"{type(e).__name__}: {str(e)}\n"
            f"Traceback:\n{traceback.format_exc()}"
        )




# =============================
# VERIFY L2TP TUNNEL
# =============================
@keyword("VERIFY L2TP TUNNEL")
def verify_l2tp_tunnel(
    protocol,
    capture_node_name, capture_node_pass,
    ping_node_name,
    capture_node_iface,
    capture_node_outer_ip, ping_node_outer_ip,
    capture_node_inner_ip, ping_node_inner_ip,
    udp_port
):
    log_message("[STEP] Starting L2TP tunnel verification")
    log_message(f"[INFO] Capture Node   : {capture_node_name}")
    log_message(f"[INFO] Ping Node      : {ping_node_name}")
    log_message(f"[INFO] Underlay IFACE : {capture_node_iface}")
    log_message(f"[INFO] Inner IPs      : {capture_node_inner_ip} -> {ping_node_inner_ip}")
    log_message(f"[INFO] Outer IPs      : {capture_node_outer_ip} -> {ping_node_outer_ip}")
    log_message(f"[INFO] UDP PORT       : {udp_port}")

    capture_node_executor = get_registered_executor(capture_node_name)
    ping_node_executor = get_registered_executor(ping_node_name)

    pcap_file = "/tmp/l2tp_capture.pcap"
    temp_file = "/tmp/ping_res.txt"

    try:
        def sudo(cmd):
            log_message(f"[CMD] sudo **** | {cmd}")
            return f"echo '{capture_node_pass}' | sudo -S {cmd}"


        tcpdump_output = {"stdout": "", "stderr": "", "failed": True}
        ping_output = {"stdout": "", "stderr": "", "failed": True}

        # -------- Detect OS + protocol --------
        os_info = capture_node_executor.execute(
            "cat /etc/os-release 2>/dev/null || true"
        ).stdout.lower()

        is_openwrt = "openwrt" in os_info
        is_mqtt = protocol.upper() == "MQTT"

    
        # ---------------- PING THREAD ----------------
        def run_ping():
            try:
               
                time.sleep(5)
                
                cmd_run = f"ping -c 5 -W 2 {capture_node_inner_ip} > {temp_file} 2>&1"
                log_message(f"[PING-START] {cmd_run}")
                ping_node_executor.execute(cmd_run)
                
                time.sleep(8)
                
                result = ping_node_executor.execute(f"cat {temp_file}")

                ping_output.update(
                    stdout=result.stdout,
                    stderr=result.stderr,
                    failed=result.failed
                )
            except Exception as e:
                ping_output["stderr"] = str(e)
                ping_output["failed"] = True
       
        # ---------------- TCPDUMP THREAD ----------------
        def run_tcpdump():
            try:
                if is_mqtt:
                    log_message("[TCPDUMP] MQTT mode → background capture")
                    capture_node_executor.execute(f"rm -f {pcap_file} 2>/dev/null || true")

                  
                    if is_openwrt:
                        start_cmd = f"tcpdump -i any -nn -U udp port {udp_port} -w {pcap_file} > /dev/null 2>&1 & echo $!"
                    else:
                        start_cmd = sudo(f"tcpdump -i any -nn -U udp port {udp_port} -w {pcap_file} > /dev/null 2>&1 & echo $!")

                    log_message(f"[TCPDUMP-MQTT-START] {start_cmd}")
                    pid_result = capture_node_executor.execute(start_cmd)
                    tcpdump_pid = pid_result.stdout.strip()

                    time.sleep(15)

                   
                    capture_node_executor.execute(f"kill -9 {tcpdump_pid} 2>/dev/null || true")
                    time.sleep(2)

                    # READ PCAP
                    read_cmd = f"tcpdump -nn -vv -r {pcap_file}"
                    result = capture_node_executor.execute(read_cmd)
                else:
                   
                    log_message("[TCPDUMP] SSH mode → live capture")
                    if is_openwrt:
                        cmd = f"tcpdump -i any -nn -vv -c 10 udp and port {udp_port}"
                    else:
                        cmd = sudo(f"tcpdump -i any -nn -vv -c 10 udp and port {udp_port}")
                    result = capture_node_executor.execute(cmd)

                tcpdump_output.update(
                    stdout=result.stdout,
                    stderr=result.stderr,
                    failed=result.failed
                )
            except Exception as e:
                tcpdump_output["stderr"] = str(e)
                tcpdump_output["failed"] = True

        # ---------------- RUN THREADS ----------------
        t1 = threading.Thread(target=run_tcpdump)
        t2 = threading.Thread(target=run_ping)

        t1.start()
        # time.sleep(5)
        t2.start()

        t1.join()
        t2.join()

        # ---------------- OUTPUT ----------------
        log_message("[OUTPUT] ===== TCPDUMP =====")
        log_message(tcpdump_output["stdout"])
        # log_message(str(tcpdump_output["stdout"]).strip())
        log_message("[OUTPUT] ===== PING =====")
        log_message(ping_output["stdout"])
        # log_message(str(ping_output["stdout"]).strip())

        # ---------------- VALIDATION ----------------
        if tcpdump_output["failed"]:
            raise AssertionError("tcpdump failed — cannot validate L2TP")

        tcpdump_lines = tcpdump_output["stdout"].splitlines()

        # ---- L2TP UDP CHECK ----
        if not any(f".{udp_port}" in l and "UDP" in l for l in tcpdump_lines):
            raise AssertionError("L2TP UDP traffic not detected")
        log_message("[OK] L2TP UDP traffic detected")

        # ---- OUTER IP CHECK ----
        outer_forward = f"{ping_node_outer_ip}.{udp_port} > {capture_node_outer_ip}.{udp_port}"
        outer_reverse = f"{capture_node_outer_ip}.{udp_port} > {ping_node_outer_ip}.{udp_port}"

        outer_fwd_hits = [l for l in tcpdump_lines if outer_forward in l]
        outer_rev_hits = [l for l in tcpdump_lines if outer_reverse in l]

        if not outer_fwd_hits:
            raise AssertionError("OUTER forward L2TP traffic missing")
        log_message("[OK] L2TP forward OUTER encapsulation detected")
        for l in outer_fwd_hits:
            log_message(f"[MATCH]     {l}")

        if not outer_rev_hits:
            raise AssertionError("OUTER reverse L2TP traffic missing")
        log_message("[OK] L2TP reverse OUTER encapsulation detected")
        for l in outer_rev_hits:
            log_message(f"[MATCH]     {l}")

        # ---- PING CHECK ----
        if ping_output["failed"]:
            raise AssertionError("Ping execution failed")

        if "0% packet loss" not in ping_output["stdout"]:
            raise AssertionError("Ping packet loss detected")

        log_message("[SUCCESS] L2TP tunnel verification PASSED")
        return True

    finally:
        capture_node_executor.execute(f"rm -f {pcap_file} 2>/dev/null || true")
        ping_node_executor.execute(f"rm -f {temp_file}")








# =============================
# TEARDOWN L2TP TUNNEL
# =============================
@keyword("TEARDOWN L2TP TUNNEL")
def teardown_l2tp_tunnel(device_name, device_pass, tunnel_id, session_id):

    log_message("========== START L2TP TEARDOWN ==========")
    log_message(f"Target Device : {device_name}")
    log_message(f"Tunnel ID     : {tunnel_id}")
    log_message(f"Session ID    : {session_id}")

    def sudo(cmd):
        log_message(f"[CMD] sudo **** | {cmd}")
        return f"echo '{device_pass}' | sudo -S {cmd}"
        
    executor = get_registered_executor(device_name)

    try:
       
            os_info = executor.execute("cat /etc/os-release 2>/dev/null || true").stdout.lower()
            is_openwrt = "openwrt" in os_info

            # Build commands
            if is_openwrt:
                del_session_cmd = (
                    f"ip l2tp del session tunnel_id {tunnel_id} "
                    f"session_id {session_id} 2>/dev/null || true"
                )
                log_message(f"[CMD] {del_session_cmd}")
             
            else:
                del_session_cmd = sudo(
                    f"ip l2tp del session tunnel_id {tunnel_id} "
                    f"session_id {session_id} 2>/dev/null || true"
                )
            
            if is_openwrt:
                del_tunnel_cmd = (
                    f"ip l2tp del tunnel tunnel_id {tunnel_id} 2>/dev/null || true"
                )
                log_message(f"[CMD] {del_tunnel_cmd}")
            else:
                del_tunnel_cmd = sudo(
                    f"ip l2tp del tunnel tunnel_id {tunnel_id} 2>/dev/null || true"
                )    

            # STEP 1: Delete L2TP session FIRST
            log_message("[STEP 1] Deleting L2TP session")
            executor.execute(del_session_cmd)
            log_message("[OK] L2TP session delete attempted")

            # STEP 2: Delete L2TP tunnel
            log_message("[STEP 2] Deleting L2TP tunnel")  
            executor.execute(del_tunnel_cmd)
            log_message("[OK] L2TP tunnel delete attempted")

            # STEP 3: Verification
            log_message("[STEP 3] Verifying L2TP interface removal")

            verify_cmd = "ip link show l2tpeth0 2>/dev/null || echo NOT_FOUND"
            result = executor.execute(verify_cmd)

            if "NOT_FOUND" not in result.stdout:
                raise AssertionError(
                    "l2tpeth0 interface still exists after teardown"
                )

            log_message("[PASS] l2tpeth0 interface removed successfully")
            log_message("========== L2TP TEARDOWN COMPLETE ==========")
            return True

    except AssertionError:
        log_message("========== L2TP TEARDOWN FAILED (ASSERTION) ==========")
        raise

    except Exception as e:
        log_message("========== L2TP TEARDOWN FAILED (EXCEPTION) ==========")
        raise AssertionError(
            f"Unexpected error during L2TP teardown on {device_name}\n"
            f"{type(e).__name__}: {str(e)}\n"
            f"Traceback:\n{traceback.format_exc()}"
        )
