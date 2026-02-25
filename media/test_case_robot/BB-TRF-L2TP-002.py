# START_DESCRIPTION     
#           1. Verify that BB and DC are reachable over both underlay paths through Path-A and Path-B.
#           2. Configure dual L2TP tunnels between BB and DC.
#           3. Assign overlay IPs and verify successful traffic forwarding between BB and DC over the L2TP tunnel.
#           4. Disable one L2TP interface and verify that traffic automatically switches to the remaining path without loss of overlay connectivity

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
# SET UP L2TP TUNNEL
# =============================    
@keyword("SET UP L2TP TUNNEL ON DUT")
def setup_l2tp_tunnel_dut(
        device_name,
        iface,
        local_ip,
        remote_ip,
        tunnel_id,
        session_id,
        peer_tunnel_id,
        peer_session_id,
        tunnel_ip,
        udp_sport,
        udp_dport, 
        loopback_ip
    ):
  


    log_message("========== START L2TP SETUP ==========")
    log_message(f"[INFO] Device           : {device_name}")
    log_message(f"[INFO] Interface        : {iface}")
    log_message(f"[INFO] Local IP         : {local_ip}")
    log_message(f"[INFO] Remote IP        : {remote_ip}")
    log_message(f"[INFO] Tunnel IDs       : {tunnel_id} <-> {peer_tunnel_id}")
    log_message(f"[INFO] Session IDs      : {session_id} <-> {peer_session_id}")
    log_message(f"[INFO] Tunnel IP        : {tunnel_ip}")
    log_message(f"[INFO] UDP Port         : {udp_sport} <-> {udp_dport}")
    
    executor = get_registered_executor(device_name)

    try:
            # STEP 0
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

            log_message("[STEP 1] Cleanup old tunnels/sessions")

            # executor.execute(
            #     f"ip l2tp del session tunnel_id {tunnel_id} session_id {session_id} 2>/dev/null || true; "
            #     f"ip l2tp del tunnel tunnel_id {tunnel_id} 2>/dev/null || true; "
            #     # f"ip link del {tunnel_iface} 2>/dev/null || true; "
            #     #f"kill $(lsof -t -i:{udp_sport}) 2>/dev/null || true"
            # )
            
            # Delete L2TP session
            executor.execute(
                    f"ip l2tp del session tunnel_id {tunnel_id} session_id {session_id} "
                    f"2>/dev/null || true"
                )

            # Delete L2TP tunnel
            executor.execute(
                    f"ip l2tp del tunnel tunnel_id {tunnel_id} "
                    f"2>/dev/null || true"
                )

            log_message("[PASS] Cleanup complete")

            log_message("[STEP 2] Creating L2TP UDP tunnel")

            tunnel_cmd = (
                f"ip l2tp add tunnel tunnel_id {tunnel_id} peer_tunnel_id {peer_tunnel_id} encap udp local {local_ip} remote {remote_ip} udp_sport {udp_sport} udp_dport {udp_dport}"
            )
            log_message(f"[CMD] {tunnel_cmd}")
            result = executor.execute(tunnel_cmd) 
            if result.failed:
                log_message("Tunnel creation failed")
                log_message(f"stdout: {result.stdout}")
                log_message(f"stderr: {result.stderr}")
                raise AssertionError(
                    f"Tunnel creation failed: {result.stderr}"
                )

            log_message("[PASS] L2TP tunnel created")

            log_message("[STEP 3] Creating L2TP session")

            sess_cmd = (
                f"ip l2tp add session "
                f"tunnel_id {tunnel_id} session_id {session_id} "
                f"peer_session_id {peer_session_id}"
            )
            log_message(f"[CMD] {sess_cmd}")
            result = executor.execute(sess_cmd)
            if result.failed:
                log_message("Session creation failed")
                log_message(f"stdout: {result.stdout}")
                log_message(f"stderr: {result.stderr}")
                raise AssertionError(
                    f"Session creation failed: {result.stderr}"
                )

            log_message("[PASS] L2TP session created")

            log_message("[STEP 4] Detecting L2TP interfaces")

            detect_iface_cmd = r"ip -o link show | grep 'l2tpeth' | awk -F': ' '{print $2}' | sed 's/://'"
            log_message(f"[CMD] {detect_iface_cmd}")
            result = executor.execute(detect_iface_cmd)

            iface_list = result.stdout.strip().splitlines()

            if not iface_list:
                log_message("No L2TP interface detected!")
                log_message(f"stdout: {result.stdout}")
                log_message(f"stderr: {result.stderr}")
                raise AssertionError(
                    f"No L2TP interface detected!: {result.stderr}"
                )

            for iface_name in iface_list:
                log_message(f"[INFO] Configuring {iface_name}")
                executor.execute(f"ip link set {iface_name} up")
                # ssh.execute(f"ip addr add {tunnel_ip}/30 dev {iface_name}")

            log_message("[PASS] L2TP interfaces configured successfully")
            log_message(f"[STEP 5] Assigning IP {tunnel_ip}/30")
            result = executor.execute(f"ip addr add {tunnel_ip}/30 dev {iface_name}")

            if result.failed:
                log_message("[WARN] IP assign failed, flushing and retrying")
                executor.execute(f"ip addr flush dev {iface_name}")
                executor.execute(f"ip addr add {tunnel_ip}/30 dev {iface_name}")

            log_message("[PASS] IP assigned")
            
            log_message("[PASS] IP assigned")    
                
            # STEP 2: Add /32 overlay to lo
           
            executor.execute(f"ip addr del {loopback_ip}/32 dev lo 2>/dev/null")
            executor.execute(f"ip addr add {loopback_ip}/32 dev lo || true")
            executor.execute(f"ip link set lo up")
            log_message("[PASS] Added source overlay to loopback")
          
            log_message("========== L2TP SETUP COMPLETE ==========")
            return 0

    
    except Exception as e:
        log_message("========== L2TP SETUP FAILED ==========")
        log_message(f"Error Type: {type(e).__name__}")
        log_message(f"Error Details: {str(e)}")
        log_message(traceback.format_exc())
        raise AssertionError(
            f"L2TP setup failed on {device_name}: {str(e)}"
        )
        
@keyword("SET UP L2TP TUNNEL ON PC")
def setup_l2tp_tunnel_pc(
        device_name,
        device_pass,
        iface,
        local_ip,
        remote_ip,
        tunnel_id,
        session_id,
        peer_tunnel_id,
        peer_session_id,
        tunnel_ip,
        udp_sport,
        udp_dport,
        loopback_ip 
    ):
  
    log_message("========== START L2TP SETUP ==========")
    log_message(f"[INFO] Device           : {device_name}")
    log_message(f"[INFO] Interface        : {iface}")
    log_message(f"[INFO] Local IP         : {local_ip}")
    log_message(f"[INFO] Remote IP        : {remote_ip}")
    log_message(f"[INFO] Tunnel IDs       : {tunnel_id} <-> {peer_tunnel_id}")
    log_message(f"[INFO] Session IDs      : {session_id} <-> {peer_session_id}")
    log_message(f"[INFO] Tunnel IP        : {tunnel_ip}")
    log_message(f"[INFO] UDP Port         : {udp_sport} <-> {udp_dport}")
    
    def sudo(cmd):
        # log_message(f"[CMD] sudo **** | {cmd}")
        return f"echo '{device_pass}' | sudo -S {cmd}"
    
    executor = get_registered_executor(device_name)

    try:
            # STEP 0
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

            log_message("[STEP 1] Cleanup old tunnels/sessions")

            # Delete L2TP session
            executor.execute(
                sudo(
                    f"ip l2tp del session tunnel_id {tunnel_id} session_id {session_id} "
                    f"2>/dev/null || true"
                )
            )
            # Delete L2TP tunnel
            executor.execute(
                sudo(
                    f"ip l2tp del tunnel tunnel_id {tunnel_id} "
                    f"2>/dev/null || true"
                )
            )
            log_message("[PASS] Cleanup complete")

            log_message("[STEP 2] Creating L2TP UDP tunnel")

            tunnel_cmd = (
                f"ip l2tp add tunnel tunnel_id {tunnel_id} peer_tunnel_id {peer_tunnel_id} encap udp local {local_ip} remote {remote_ip} udp_sport {udp_sport} udp_dport {udp_dport}"
            )
            log_message(f"[CMD] {tunnel_cmd}")
            result = executor.execute(sudo(tunnel_cmd)) 
            if result.failed:
                log_message("Tunnel creation failed")
                log_message(f"stdout: {result.stdout}")
                log_message(f"stderr: {result.stderr}")
                raise AssertionError(
                    f"Tunnel creation failed: {result.stderr}"
                )

            log_message("[PASS] L2TP tunnel created")

            log_message("[STEP 3] Creating L2TP session")

            sess_cmd = (
                f"ip l2tp add session "
                f"tunnel_id {tunnel_id} session_id {session_id} "
                f"peer_session_id {peer_session_id}"
            )
            log_message(f"[CMD] {sess_cmd}")
            result = executor.execute(sudo(sess_cmd))
            if result.failed:
                log_message("Session creation failed")
                log_message(f"stdout: {result.stdout}")
                log_message(f"stderr: {result.stderr}")
                raise AssertionError(
                    f"Session creation failed: {result.stderr}"
                )

            log_message("[PASS] L2TP session created")

            log_message("[STEP 4] Detecting L2TP interfaces")

            detect_iface_cmd = r"ip -o link show | grep 'l2tpeth' | awk -F': ' '{print $2}' | sed 's/://'"
            log_message(f"[CMD] {detect_iface_cmd}")
            result = executor.execute(detect_iface_cmd)

            iface_list = result.stdout.strip().splitlines()

            if not iface_list:
                log_message("No L2TP interface detected!")
                log_message(f"stdout: {result.stdout}")
                log_message(f"stderr: {result.stderr}")
                raise AssertionError(
                    f"No L2TP interface detected!: {result.stderr}"
                )

            for iface_name in iface_list:
                log_message(f"[INFO] Configuring {iface_name}")
                executor.execute(sudo(f"ip link set {iface_name} up"))
                # ssh.execute(f"ip addr add {tunnel_ip}/30 dev {iface_name}")

            log_message("[PASS] L2TP interfaces configured successfully")
            log_message(f"[STEP 5] Assigning IP {tunnel_ip}/30")
            result = executor.execute(sudo(f"ip addr add {tunnel_ip}/30 dev {iface_name}"))

            if result.failed:
                log_message("[WARN] IP assign failed, flushing and retrying")
                executor.execute(sudo(f"ip addr flush dev {iface_name}"))
                executor.execute(sudo(f"ip addr add {tunnel_ip}/30 dev {iface_name}"))
            
            log_message("[PASS] IP assigned")    
                
            # STEP 2: Add /32 overlay to lo
           
            executor.execute(sudo(f"ip addr del {loopback_ip}/32 dev lo 2>/dev/null"))
            executor.execute(sudo(f"ip addr add {loopback_ip}/32 dev lo || true"))
            executor.execute(sudo(f"ip link set lo up"))
            log_message("[PASS] Added source overlay to loopback")
    
            log_message("========== L2TP SETUP COMPLETE ==========")
            return 0

    
    except Exception as e:
        log_message("========== L2TP SETUP FAILED ==========")
        log_message(f"Error Type: {type(e).__name__}")
        log_message(f"Error Details: {str(e)}")
        log_message(traceback.format_exc())
        raise AssertionError(
            f"L2TP setup failed on {device_name}: {str(e)}"
        )        
    
# ===================================
# Configure Active / Standby Routing
# ===================================
@keyword("CONFIGURE ROUTING SETUP ON DUT")
def configure_routing_setup_dut(
    device_name,
    dst_lo_ip,
    metric_a=100,
    metric_b=200
):

    log_message("========== ROUTE SETUP START ==========")
    log_message(f"Target Device: {device_name}")
    log_message(f"Desitnation Loopback IP: {dst_lo_ip}")
    
    
    executor = get_registered_executor(device_name)
   

    try:    
            
            # STEP 1: Detect all L2TP interfaces (l2tpeth*)
            
            detect_cmd = r"ip -o link show | grep 'l2tpeth' | awk -F': ' '{print $2}' | sed 's/://'"
            result = executor.execute(detect_cmd)

            iface_list = result.stdout.strip().splitlines()

            if len(iface_list) < 2:
                log_message("[FAIL] Need at least 2 L2TP interfaces for active and standby routing")
                log_message(f"Detected interfaces: {iface_list}")
                return 1

            # Ensure sorted order like l2tpeth0, l2tpeth1
            iface_list = sorted(iface_list)

            l2tp_iface_a = iface_list[0]
            l2tp_iface_b = iface_list[1]

            log_message(f"[INFO] Using L2TP interfaces: {l2tp_iface_a}, {l2tp_iface_b}")
            
            log_message("[STEP 1] Verification")

            log_message("---- L2TP Tunnel ----")
            log_message(executor.execute("ip l2tp show tunnel").stdout)

            log_message("---- L2TP Session ----")
            log_message(executor.execute("ip l2tp show session").stdout)
          
            # STEP 2:Configure Active / Standby Routing (Multipath Routing)
            log_message("[STEP 2] Configure Active / Standby Routing (Multipath Routing)")
            nexthop_route= (f"ip route replace {dst_lo_ip}/32 \
                nexthop dev {l2tp_iface_a} weight 1 \
                nexthop dev {l2tp_iface_b} weight 1"
                )
            log_message(f"[CMD] {nexthop_route}")
            executor.execute(nexthop_route)

            log_message("[PASS]routing configured successfully")
            log_message("========== ROUTE SETUP COMPLETE ==========")
            return 0

    except Exception as e:
        log_message("========== ROUTING FAILED ==========")
        log_message(f"Error Type: {type(e).__name__}")
        log_message(f"Error Details: {str(e)}")
        log_message(traceback.format_exc())
        raise AssertionError(
            f"routing failed on {device_name}: {str(e)}"
        )  
        
@keyword("CONFIGURE ROUTING SETUP ON PC")
def configure_routing_setup_pc(
    device_name,
    device_pass,
    dst_lo_ip,
    metric_a=100,
    metric_b=200
):

    log_message("========== ROUTE SETUP START ==========")
    log_message(f"Target Device: {device_name}")
    log_message(f"Desitnation Loopback IP: {dst_lo_ip}")
    
    def sudo(cmd):
        # log_message(f"[CMD] sudo **** | {cmd}")
        return f"echo '{device_pass}' | sudo -S {cmd}"
    
    executor = get_registered_executor(device_name)
  
    try:    
            # STEP 1: Detect all L2TP interfaces (l2tpeth*)
            detect_cmd = r"ip -o link show | grep 'l2tpeth' | awk -F': ' '{print $2}' | sed 's/://'"
            result = executor.execute(detect_cmd)

            iface_list = result.stdout.strip().splitlines()

            if len(iface_list) < 2:
                log_message("[FAIL] Need at least 2 L2TP interfaces for active and standby routing")
                log_message(f"Detected interfaces: {iface_list}")
                return 1

            # Ensure sorted order like l2tpeth0, l2tpeth1
            iface_list = sorted(iface_list)

            l2tp_iface_a = iface_list[0]
            l2tp_iface_b = iface_list[1]

            log_message(f"[INFO] Using L2TP interfaces: {l2tp_iface_a}, {l2tp_iface_b}")
            
            log_message("[STEP 1] Verification")

            log_message("---- L2TP Tunnel ----")
            log_message(executor.execute(sudo("ip l2tp show tunnel")).stdout)

            log_message("---- L2TP Session ----")
            log_message(executor.execute(sudo("ip l2tp show session")).stdout)

            # STEP 2:Configure Active / Standby Routing (Multipath Routing)
            log_message("[STEP 2] Configure Active / Standby Routing (Multipath Routing)")
            nexthop_route= (f"ip route replace {dst_lo_ip}/32 \
                nexthop dev {l2tp_iface_a} weight 1 \
                nexthop dev {l2tp_iface_b} weight 1"
                )
            log_message(f"[CMD] {nexthop_route}")
            executor.execute(sudo(nexthop_route))

            log_message("[PASS]routing configured successfully")
            log_message("========== ROUTE SETUP COMPLETE ==========")
            return 0
        
    except Exception as e:
        log_message("========== ROUTING FAILED ==========")
        log_message(f"Error Type: {type(e).__name__}")
        log_message(f"Error Details: {str(e)}")
        log_message(traceback.format_exc())
        raise AssertionError(
            f"routing failed on {device_name}: {str(e)}"
        )  
        


# =============================
# VERIFY L2TP REDUNDANCY
# =============================
@keyword("VERIFY L2TP REDUNDANCY ON DUT")
def verify_l2tp_redundancy_dut(
    device_name, 
    target_overlay_ip,
    ping_interval=1,
    iface_timeout=60
):

    log_message("========== START L2TP REDUNDANCY VERIFICATION ==========")
    log_message(f"Target Device: {device_name}")
    log_message(f"Overlay Target: {target_overlay_ip}")
    
    executor = get_registered_executor(device_name)

    ping_state = {
        "alive": False,
        "stop": False,
        "last_success": 0.0,
        "success_count": 0,
        "last_output": ""
    }
    ping_thread_ref = None

    def run(cmd, ssh):
        log_message(f"[CMD] {cmd}")
        res = ssh.execute(cmd)
        out = (res.stdout or "").strip()
        if out:
            for line in out.splitlines():
                log_message(f"[OUTPUT] {line}")
        err = (res.stderr or "").strip()
        if err:
            for line in err.splitlines():
                log_message(f"[ERROR] {line}")
        return res

    try:
             # STEP 1: Detect all L2TP interfaces (l2tpeth*)
            
            detect_cmd = r"ip -o link show | grep 'l2tpeth' | awk -F': ' '{print $2}' | sed 's/://'"
            result = executor.execute(detect_cmd)

            iface_list = result.stdout.strip().splitlines()

            if len(iface_list) < 2:
                log_message("[FAIL] Need at least 2 L2TP interfaces for ECMP")
                log_message(f"Detected interfaces: {iface_list}")
                return 1

            # Ensure sorted order like l2tpeth0, l2tpeth1
            iface_list = sorted(iface_list)

            l2tp_iface_a = iface_list[0]
            l2tp_iface_b = iface_list[1]

            log_message(f"[INFO] Using ECMP interfaces: {l2tp_iface_a}, {l2tp_iface_b}")
            def ping_thread():
                while not ping_state["stop"]:
                    try:
                        res = executor.execute(f"ping -c 1 {target_overlay_ip}")
                        text = ((res.stdout or "") + "\n" + (res.stderr or "")).strip()
                        if text:
                            for line in text.splitlines():
                                log_message(f"[PING] {line}")

                        success = (
                            "bytes from" in text
                            or "1 received" in text
                            or " ttl=" in text
                        )
                        if success:
                            ping_state["alive"] = True
                            ping_state["last_success"] = time.time()
                            ping_state["success_count"] += 1
                        else:
                            ping_state["alive"] = False

                    except Exception as ex:
                        log_message(f"[PING THREAD ERROR] {type(ex).__name__}: {str(ex)}")
                        ping_state["alive"] = False

                    time.sleep(ping_interval)

            ping_thread_ref = threading.Thread(target=ping_thread, daemon=True)
            ping_thread_ref.start()

            # BASELINE
            log_message("[BASELINE] Waiting for at least 3 successful pings...")
            baseline_start = time.time()
            while True:
                if ping_state["success_count"] >= 3:
                    log_message(f"[BASELINE] OK — {ping_state['success_count']} successful pings")
                    break
                if time.time() - baseline_start > iface_timeout:
                    ping_state["stop"] = True
                    ping_thread_ref.join()
                    raise AssertionError(
                        f"Baseline failed — only {ping_state['success_count']} successful pings"
                    )
                time.sleep(1)

            # TEST1 — A DOWN
            log_message("[TEST 1] Bringing L2TP-A DOWN")
            pre_time = ping_state["last_success"]
            run(f"ip link set {l2tp_iface_a} down", executor)
            
             #Check route
            log_message("[TEST 1] Check Route")
            run(f"ip route get {target_overlay_ip}", executor) 

            log_message("[TEST 1] Waiting recovery") 
            fail_start = time.time()
            while time.time() - fail_start <= iface_timeout:
                if ping_state["last_success"] > pre_time:
                    break
                time.sleep(0.2)
            else:
                run(f"ip link set {l2tp_iface_a} up", executor)
                ping_state["stop"] = True
                ping_thread_ref.join()
                raise AssertionError("L2TP-A failover failed — no ping recovered")

            run(f"ip link set {l2tp_iface_a} up", executor)
            time.sleep(2)

            # TEST2 — B DOWN
            log_message("[TEST 2] Bringing L2TP-B DOWN")
            pre_time = ping_state["last_success"]
            run(f"ip link set {l2tp_iface_b} down", executor)
            
             #Check route
            log_message("[TEST 2] Check Route")
            run(f"ip route get {target_overlay_ip}", executor) 

            log_message("[TEST 2] Waiting recovery")
            fail_start = time.time()
            while time.time() - fail_start <= iface_timeout:
                if ping_state["last_success"] > pre_time:
                    break
                time.sleep(0.2)
            else:
                run(f"ip link set {l2tp_iface_b} up", executor)
                ping_state["stop"] = True
                ping_thread_ref.join()
                raise AssertionError("L2TP-B failover failed — no ping recovered")

            run(f"ip link set {l2tp_iface_b} up", executor)
            time.sleep(2)

            ping_state["stop"] = True
            ping_thread_ref.join()
            log_message("========== L2TP REDUNDANCY TEST PASSED ==========")

    except Exception as ex:
        ping_state["stop"] = True
        if ping_thread_ref:
            ping_thread_ref.join()
        raise AssertionError(
            f"L2TP redundancy verification failed: {str(ex)}"
        )
        
@keyword("VERIFY L2TP REDUNDANCY ON PC")
def verify_l2tp_redundancy_pc(
    device_name,device_pass, 
    target_overlay_ip,
    ping_interval=1,
    iface_timeout=60
):

    log_message("========== START L2TP REDUNDANCY VERIFICATION ==========")
    log_message(f"Target Device: {device_name}")
    log_message(f"Overlay Target: {target_overlay_ip}")
    
    executor = get_registered_executor(device_name)

    ping_state = {
        "alive": False,
        "stop": False,
        "last_success": 0.0,
        "success_count": 0,
        "last_output": ""
    }
    ping_thread_ref = None

    def run(cmd, ssh):
        log_message(f"[CMD] {cmd}")
        full = f"echo '{device_pass}' | sudo -S {cmd}"
        res = ssh.execute(full)
        out = (res.stdout or "").strip()
        if out:
            for line in out.splitlines():
                log_message(f"[OUTPUT] {line}")
        err = (res.stderr or "").strip()
        if err:
            for line in err.splitlines():
                log_message(f"[ERROR] {line}")
        return res

    try:
             # STEP 1: Detect all L2TP interfaces (l2tpeth*)
            
            detect_cmd = r"ip -o link show | grep 'l2tpeth' | awk -F': ' '{print $2}' | sed 's/://'"
            result = executor.execute(detect_cmd)

            iface_list = result.stdout.strip().splitlines()

            if len(iface_list) < 2:
                log_message("[FAIL] Need at least 2 L2TP interfaces for ECMP")
                log_message(f"Detected interfaces: {iface_list}")
                return 1

            # Ensure sorted order like l2tpeth0, l2tpeth1
            iface_list = sorted(iface_list)

            l2tp_iface_a = iface_list[0]
            l2tp_iface_b = iface_list[1]

            log_message(f"[INFO] Using ECMP interfaces: {l2tp_iface_a}, {l2tp_iface_b}")
            def ping_thread():
                while not ping_state["stop"]:
                    try:
                        res = executor.execute(f"ping -c 1 {target_overlay_ip}")
                        text = ((res.stdout or "") + "\n" + (res.stderr or "")).strip()
                        if text:
                            for line in text.splitlines():
                                log_message(f"[PING] {line}")

                        success = (
                            "bytes from" in text
                            or "1 received" in text
                            or " ttl=" in text
                        )
                        if success:
                            ping_state["alive"] = True
                            ping_state["last_success"] = time.time()
                            ping_state["success_count"] += 1
                        else:
                            ping_state["alive"] = False

                    except Exception as ex:
                        log_message(f"[PING THREAD ERROR] {type(ex).__name__}: {str(ex)}")
                        ping_state["alive"] = False

                    time.sleep(ping_interval)

            ping_thread_ref = threading.Thread(target=ping_thread, daemon=True)
            ping_thread_ref.start()

            # BASELINE
            log_message("[BASELINE] Waiting for at least 3 successful pings...")
            baseline_start = time.time()
            while True:
                if ping_state["success_count"] >= 3:
                    log_message(f"[BASELINE] OK — {ping_state['success_count']} successful pings")
                    break
                if time.time() - baseline_start > iface_timeout:
                    ping_state["stop"] = True
                    ping_thread_ref.join()
                    raise AssertionError(
                        f"Baseline failed — only {ping_state['success_count']} successful pings"
                    )
                time.sleep(1)

            # TEST1 — A DOWN
            log_message("[TEST 1] Bringing L2TP-A DOWN")
            pre_time = ping_state["last_success"]
            run(f"ip link set {l2tp_iface_a} down", executor)
            
             #Check route
            log_message("[TEST 1] Check Route")
            run(f"ip route get {target_overlay_ip}", executor) 

            log_message("[TEST 1] Waiting recovery") 
            fail_start = time.time()
            while time.time() - fail_start <= iface_timeout:
                if ping_state["last_success"] > pre_time:
                    break
                time.sleep(0.2)
            else:
                run(f"ip link set {l2tp_iface_a} up", executor)
                ping_state["stop"] = True
                ping_thread_ref.join()
                raise AssertionError("L2TP-A failover failed — no ping recovered")

            run(f"ip link set {l2tp_iface_a} up", executor)
            time.sleep(2)

            # TEST2 — B DOWN
            log_message("[TEST 2] Bringing L2TP-B DOWN")
            pre_time = ping_state["last_success"]
            run(f"ip link set {l2tp_iface_b} down", executor)
            
             #Check route
            log_message("[TEST 2] Check Route")
            run(f"ip route get {target_overlay_ip}", executor) 

            log_message("[TEST 2] Waiting recovery")
            fail_start = time.time()
            while time.time() - fail_start <= iface_timeout:
                if ping_state["last_success"] > pre_time:
                    break
                time.sleep(0.2)
            else:
                run(f"ip link set {l2tp_iface_b} up", executor)
                ping_state["stop"] = True
                ping_thread_ref.join()
                raise AssertionError("L2TP-B failover failed — no ping recovered")

            run(f"ip link set {l2tp_iface_b} up", executor)
            time.sleep(2)

            ping_state["stop"] = True
            ping_thread_ref.join()
            log_message("========== L2TP REDUNDANCY TEST PASSED ==========")

    except Exception as ex:
        ping_state["stop"] = True
        if ping_thread_ref:
            ping_thread_ref.join()
        raise AssertionError(
            f"L2TP redundancy verification failed: {str(ex)}"
        )
        

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
