# START_DESCRIPTION       
#           1. Verify that BB and DC are reachable over both underlay paths through Path-A and Path-B.
#           2. Configure dual GRE tunnels between BB and DC.
#           3. Assign overlay IPs and verify successful traffic forwarding between BB and DC over the GRE tunnel.
#           4. Disable one GRE interface and verify that traffic automatically switches to the remaining path without loss of overlay connectivity
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

@keyword("GRE REDUNDANCY TOPOLOGY")
def topology(dc_eth1, dc_eth2,dc_ip1,dc_ip2,bb_eth1, bb_eth2,bb_ip1,bb_ip2):
    log_message(f"""
            +---------------------+
            |   DC [Data-Center]   |
            | {dc_eth1}: {dc_ip1}  |
            | {dc_eth2}: {dc_ip2}  |
            +---------+-----------+
                      |
       ---------------+----------------
       |                              |
+------+-------+             +-------+------+
|    RPI-1     |             |    RPI-2     |
+-------+------+             +-------+------+
      |                              |
      +---------------+--------------+
                      | 
            +---------+----------+
            |  BB [BlackBox]     |
            |{bb_eth1}: {bb_ip1} |
            |{bb_eth2}: {bb_ip2} |
            +---------+----------+
     STEP:       
          1. Verify that BB and DC are reachable over both underlay paths through Path-A and Path-B.
          2. Configure dual GRE tunnels between BB and DC.
          3. Assign overlay IPs and verify successful traffic forwarding between BB and DC over the GRE tunnel.
          4. Disable one GRE interface and verify that traffic automatically switches to the remaining path without loss of overlay connectivity
""")

# =============================
# SET UP GRE TUNNEL
# =============================
@keyword("SET UP GRE TUNNEL ON BB")
def setup_gre_tunnel_bb(device_name, tunnel_name, underlay_iface, local_ip, remote_ip, tunnel_ip):
    
    log_message("========== START GRE SETUP ON BB ==========")
    log_message(f"Target Device: {device_name}")
    log_message(f"GRE Tunnel: {tunnel_name}")
    log_message(f"Local → Remote: {local_ip} → {remote_ip}")
    log_message(f"Tunnel IP: {tunnel_ip}")
    
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
            
            # STEP 1
            log_message("[STEP 1] Cleaning up old GRE interface")
            cleanup_cmd = f"ip link del {tunnel_name} 2>/dev/null || true"
            executor.execute(cleanup_cmd)
            log_message("Old GRE interface cleanup completed")

            # STEP 2
            log_message("[STEP 2] Creating GRE tunnel")
            create_cmd = (
                f"ip tunnel add {tunnel_name} mode gre "
                f"remote {remote_ip} local {local_ip} ttl 255 dev {underlay_iface}"
            )
            log_message(f"[CMD] {create_cmd}")
            result = executor.execute(create_cmd)
            if result.failed:
                raise AssertionError(
                    f"GRE tunnel creation failed\nstdout:{result.stdout}\nstderr:{result.stderr}"
                )

            log_message("GRE tunnel created successfully")

            # STEP 3
            log_message("[STEP 3] Bringing GRE interface UP")
            result = executor.execute(f"ip link set {tunnel_name} up")
            if result.failed:
                raise AssertionError("Failed to bring up GRE interface")

            log_message("GRE interface is UP")

            # STEP 4
            log_message(f"[STEP 4] Assigning IP {tunnel_ip}/30 to {tunnel_name}")
            result = executor.execute(f"ip addr add {tunnel_ip}/30 dev {tunnel_name}")
            if result.failed:
                raise AssertionError("Failed to assign tunnel IP")

            log_message("Tunnel IP assigned successfully")
            log_message(f"========== {device_name}: GRE TUNNEL {tunnel_name} -- {tunnel_ip} SETUP COMPLETE ==========")

    except Exception as e:
        log_message("========== GRE SETUP FAILED ==========")
        log_message(f"Exception: {type(e).__name__}")
        log_message(str(e))
        log_message(traceback.format_exc())
        raise AssertionError(f"GRE setup failed on {device_name}: {e}")

### FUNCTION WITH SUDO AND PASSWORD###########
@keyword("SET UP GRE TUNNEL ON DC")
def setup_gre_tunnel_dc(device_name, pc_pass,
                        tunnel_name, underlay_iface,
                        local_ip, remote_ip, tunnel_ip):


    log_message("========== START GRE SETUP ON DC ==========")
    log_message(f"Target Device: {device_name}")
    log_message(f"GRE Tunnel: {tunnel_name}")
    log_message(f"Local → Remote: {local_ip} → {remote_ip}")
    log_message(f"Tunnel IP: {tunnel_ip}")
    
    
    def sudo(cmd):
        log_message(f"[CMD] sudo **** | {cmd}")
        return f"echo '{pc_pass}' | sudo -S {cmd}"
    
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
        
            # STEP 1
            log_message("[STEP 1] Cleaning up old GRE interface")
            executor.execute( sudo(f"ip link del {tunnel_name} 2>/dev/null || true") )

            # STEP 2
            log_message("[STEP 2] Creating GRE tunnel")
            create_cmd = sudo(
                f"ip tunnel add {tunnel_name} mode gre "
                f"remote {remote_ip} local {local_ip} ttl 255 dev {underlay_iface}"
            )
            res = executor.execute(create_cmd)
            if res.failed:
                raise AssertionError(
                    f"GRE tunnel creation failed\nstdout:{res.stdout}\nstderr:{res.stderr}"
                )

            # STEP 3
            log_message("[STEP 3] Bringing GRE interface UP")
            res = executor.execute(sudo(f"ip link set {tunnel_name} up"))
            if res.failed:
                raise AssertionError("Failed to bring up GRE interface")

            # STEP 4
            log_message(f"[STEP 4] Assigning IP {tunnel_ip}/30 to {tunnel_name}")
            res = executor.execute(sudo(f"ip addr add {tunnel_ip}/30 dev {tunnel_name}"))
            if res.failed:
                raise AssertionError("Failed to assign tunnel IP")

            log_message(f"========== {device_name}: GRE TUNNEL {tunnel_name} -- {tunnel_ip} SETUP COMPLETE ==========")

    except Exception as e:
        log_message("========== GRE SETUP FAILED ==========")
        log_message(f"{type(e).__name__}: {e}")
        log_message(traceback.format_exc())
        raise AssertionError(f"GRE setup failed on {device_name}: {e}")

    
# =============================
# Add ECMP Route (Load-Balanced)
# =============================
@keyword("ECMP ROUTE SETUP ON BB")
def ecmp_route_setup_bb(
    device_name, 
    src_tunnel_ip, dst_tunnel_ip,
    dst_gre_a_ip, dst_gre_b_ip,
    gre_a_name="gre1", gre_b_name="gre2",
    weight_a=1, weight_b=1
):
    log_message("========== ECMP ROUTE SETUP START ON BB ==========")
    log_message(f"DUT: {device_name}")
    log_message(f"Source Overlay IP: {src_tunnel_ip}")
    log_message(f"Destination Overlay IP: {dst_tunnel_ip}")
    log_message(f"NextHop A: via {dst_gre_a_ip} dev {gre_a_name} weight {weight_a}")
    log_message(f"NextHop B: via {dst_gre_b_ip} dev {gre_b_name} weight {weight_b}")
    
    executor = get_registered_executor(device_name)

    try:
           
            log_message("[STEP 1] Add overlay /32 to loopback (idempotent)")
            executor.execute(f"ip addr del {src_tunnel_ip}/32 dev lo 2>/dev/null")
            executor.execute(f"ip addr add {src_tunnel_ip}/32 dev lo || true")

            log_message("[STEP 2] Remove old ECMP route if exists")
            executor.execute(f"ip route del {dst_tunnel_ip}/32 || true")

            log_message("[STEP 3] Apply ECMP routing")
            create_cmd = (
                f"ip route add {dst_tunnel_ip}/32 "
                f"nexthop via {dst_gre_a_ip} dev {gre_a_name} weight {weight_a} "
                f"nexthop via {dst_gre_b_ip} dev {gre_b_name} weight {weight_b}"
            )
            log_message(f"[CMD] {create_cmd}")
            
            result = executor.execute(create_cmd)

            if result.failed:
                log_message("ECMP routing FAILED")
                log_message(f"stdout: {result.stdout}")
                log_message(f"stderr: {result.stderr}")
                raise AssertionError(
                    f"ECMP route creation failed: {result.stderr}"
                )

            log_message("ECMP routing configured successfully")
            return 0

    except Exception as e:
        log_message("========== ECMP ROUTING FAILED ==========")
        log_message(f"Error Type: {type(e).__name__}")
        log_message(f"Error Details: {str(e)}")
        log_message(traceback.format_exc())
        raise AssertionError(
            f"ECMP routing failed on {device_name}: {str(e)}"
        )


############SUDO AND PASSWORD#############
@keyword("ECMP ROUTE SETUP ON DC")
def ecmp_route_setup_dc(
    device_name, dut_pass,
    src_tunnel_ip, dst_tunnel_ip,
    dst_gre_a_ip, dst_gre_b_ip,
    gre_a_name="gre1", gre_b_name="gre2",
    weight_a=1, weight_b=1
):
    log_message("========== ECMP ROUTE SETUP START ON DC ==========")
    
    executor = get_registered_executor(device_name)

    def sudo(ssh, cmd):
        log_message(f"[CMD] sudo **** | {cmd}")
        full = f"echo '{dut_pass}' | sudo -S {cmd}"
        return ssh.execute(full)

    try:
        
            log_message("[STEP 1] Add overlay /32 to loopback (idempotent)")
            sudo(executor, f"ip addr del {src_tunnel_ip}/32 dev lo 2>/dev/null || true")
            sudo(executor, f"ip addr add {src_tunnel_ip}/32 dev lo || true")

            log_message("[STEP 2] Remove old ECMP route if exists")
            sudo(executor, f"ip route del {dst_tunnel_ip}/32 || true")

            log_message("[STEP 3] Apply ECMP routing")
            create_cmd = (
                f"ip route add {dst_tunnel_ip}/32 "
                f"nexthop via {dst_gre_a_ip} dev {gre_a_name} weight {weight_a} "
                f"nexthop via {dst_gre_b_ip} dev {gre_b_name} weight {weight_b}"
            )
            

            result = sudo(executor, create_cmd)

            if result.failed:
                log_message("ECMP routing FAILED")
                log_message(f"stdout: {result.stdout}")
                log_message(f"stderr: {result.stderr}")
                raise AssertionError(
                    f"ECMP route creation failed: {result.stderr}"
                )

            log_message("ECMP routing configured successfully")
            return 0

    except Exception as e:
        log_message("========== ECMP ROUTING FAILED  ==========")
        log_message(f"Error Type: {type(e).__name__}")
        log_message(f"Error Details: {str(e)}")
        log_message(traceback.format_exc())
        raise AssertionError(
            f"ECMP routing failed on {device_name}: {str(e)}"
        )


# =============================
# VERIFY GRE REDUNDANCY
# =============================
@keyword("VERIFY GRE REDUNDANCY ON BB")
def verify_gre_redundancy_bb(
        device_name, 
        gre_a_name, gre_b_name,
        target_overlay_ip,
        ping_interval=1,
        iface_timeout=60
    ):
    log_message("========== START GRE REDUNDANCY VERIFICATION ON BB ==========")
    log_message(f"DUT: {device_name}")
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
            log_message("[TEST 1] Bringing GRE-A DOWN")
            pre_time = ping_state["last_success"]
            run(f"ip link set {gre_a_name} down", executor)

            log_message("[TEST 1] Waiting recovery")
            fail_start = time.time()
            while time.time() - fail_start <= iface_timeout:
                if ping_state["last_success"] > pre_time:
                    break
                time.sleep(0.2)
            else:
                run(f"ip link set {gre_a_name} up", executor)
                ping_state["stop"] = True
                ping_thread_ref.join()
                raise AssertionError("GRE-A failover failed — no ping recovered")

            run(f"ip link set {gre_a_name} up", executor)
            time.sleep(2)

            # TEST2 — B DOWN
            log_message("[TEST 2] Bringing GRE-B DOWN")
            pre_time = ping_state["last_success"]
            run(f"ip link set {gre_b_name} down", executor)

            log_message("[TEST 2] Waiting recovery")
            fail_start = time.time()
            while time.time() - fail_start <= iface_timeout:
                if ping_state["last_success"] > pre_time:
                    break
                time.sleep(0.2)
            else:
                run(f"ip link set {gre_b_name} up", executor)
                ping_state["stop"] = True
                ping_thread_ref.join()
                raise AssertionError("GRE-B failover failed — no ping recovered")

            run(f"ip link set {gre_b_name} up", executor)
            time.sleep(2)

            ping_state["stop"] = True
            ping_thread_ref.join()
            log_message("========== GRE REDUNDANCY TEST PASSED ==========")

    except Exception as ex:
        ping_state["stop"] = True
        if ping_thread_ref:
            ping_thread_ref.join()
        raise AssertionError(
            f"GRE redundancy verification failed: {str(ex)}"
        )
##=================DC================
#############SUDO AND PASSWORD##############
@keyword("VERIFY GRE REDUNDANCY ON DC")
def verify_gre_redundancy_dc(
        device_name, device_pass,
        gre_a_name, gre_b_name,
        target_overlay_ip,
        ping_interval=1,
        iface_timeout=60
    ):
    log_message("========== START GRE REDUNDANCY VERIFICATION ON DC ==========")
    log_message(f"DUT: {device_name}")
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
            log_message("[TEST 1] Bringing GRE-A DOWN")
            pre_time = ping_state["last_success"]
            run(f"ip link set {gre_a_name} down", executor)

            log_message("[TEST 1] Waiting recovery")
            fail_start = time.time()
            while time.time() - fail_start <= iface_timeout:
                if ping_state["last_success"] > pre_time:
                    break
                time.sleep(0.2)
            else:
                run(f"ip link set {gre_a_name} up", executor)
                ping_state["stop"] = True
                ping_thread_ref.join()
                raise AssertionError("GRE-A failover failed — no ping recovered")

            run(f"ip link set {gre_a_name} up", executor)
            time.sleep(2)

            # TEST2 — B DOWN
            log_message("[TEST 2] Bringing GRE-B DOWN")
            pre_time = ping_state["last_success"]
            run(f"ip link set {gre_b_name} down", executor)

            log_message("[TEST 2] Waiting recovery")
            fail_start = time.time()
            while time.time() - fail_start <= iface_timeout:
                if ping_state["last_success"] > pre_time:
                    break
                time.sleep(0.2)
            else:
                run(f"ip link set {gre_b_name} up", executor)
                ping_state["stop"] = True
                ping_thread_ref.join()
                raise AssertionError("GRE-B failover failed — no ping recovered")

            run(f"ip link set {gre_b_name} up", executor)
            time.sleep(2)

            ping_state["stop"] = True
            ping_thread_ref.join()
            log_message("========== GRE REDUNDANCY TEST PASSED ==========")

    except Exception as ex:
        ping_state["stop"] = True
        if ping_thread_ref:
            ping_thread_ref.join()
        raise AssertionError(
            f"GRE redundancy verification failed: {str(ex)}"
        )

# =============================
# TEARDOWN GRE TUNNEL
# =============================
@keyword("TEARDOWN GRE TUNNEL")
def teardown_gre_tunnel(device_name,device_pass,tunnel_name):
    log_message(f"Target Device: {device_name}")
    log_message(f"GRE Interface: {tunnel_name}")
    
    def sudo(cmd):
        log_message(f"[CMD] sudo **** | {cmd}")
        return f"echo '{device_pass}' | sudo -S {cmd}"
    
    executor = get_registered_executor(device_name)
    try:
        
        log_message("[STEP 1] Removing GRE interface")
            # Detect OS
        os_info = executor.execute("cat /etc/os-release 2>/dev/null || true").stdout.lower()
        if "openwrt" in os_info:
                cmd = f"ip link del {tunnel_name} 2>/dev/null || true"
                log_message(f"[CMD] {cmd}")
        else:
                cmd = sudo(f"ip link del {tunnel_name} 2>/dev/null || true")
        result = executor.execute(cmd)
        if result.failed:
                raise AssertionError(
                    f"GRE tunnel teardown failed on {device_name}\n"
                    f"stdout: {result.stdout}\n"
                    f"stderr: {result.stderr}"
                )
        log_message("GRE interface removed")
        return True

    except Exception as e:
        log_message("GRE teardown failed due to exception")
        log_message(str(e))
        log_message(traceback.format_exc())
        return False

