# START_DESCRIPTION       
#           1. Verify that BB and DC are reachable over both underlay paths through Path-A and Path-B.
#           2. Configure dual VxLAN tunnels between BB and DC.
#           3. Assign overlay IPs and verify successful traffic forwarding between BB and DC over the GRE tunnel.
#           4. Disable one VxLAN interface and verify that traffic automatically switches to the remaining path without loss of overlay connectivity
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
# SET UP DUAL VXLAN TUNNEL
# =============================
@keyword("SETUP VXLAN TUNNEL ON BB")
def setup_vxlan_tunnel_bb(
    device_name,
    name,
    vxlan_id,
    iface,
    local_ip,
    remote_ip
):
    
    log_message("========== START VXLAN SETUP ==========")
    log_message(f"Target Device : {device_name}")
    log_message(f"VXLAN_NAME: {name}, VXLAN_ID={vxlan_id}, INTERFACE={iface},  LOCAL_IP={local_ip},  REMOTE_IP={remote_ip}")
    
    
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
            
            log_message("[STEP 1] Cleanup any existing objects")
            executor.execute(f"ip link del {name} 2>/dev/null || true")

            # Create VXLAN
            log_message(f"[STEP 2] Creating {name}")
            cmd = (
                f"ip link add {name} type vxlan id {vxlan_id} "
                f"local {local_ip} remote {remote_ip} "
                f"dstport 4789 dev {iface}"
            )

            log_message(f"[CMD] {cmd}")
            res = executor.execute(cmd)
            if res.failed:
                raise AssertionError(
                    f"VxLAN tunnel creation failed\nstdout:{res.stdout}\nstderr:{res.stderr}"
                )

            log_message(f"[OK] Tunnel {name} created successfully")

            log_message(f"========== VxLAN SETUP COMPLETE FOR {device_name}<->{name} ==========")
            time.sleep(2)
            return 0

    except Exception as e:
        log_message("========== VxLAN SETUP FAILED ==========")
        log_message(f"Exception: {type(e).__name__}")
        log_message(str(e))
        log_message(traceback.format_exc())
        raise AssertionError(f"VxLAN setup failed on {device_name}: {e}")

@keyword("SETUP VXLAN TUNNEL ON DC")
def setup_vxlan_tunnel_dc(
    device_name,
    device_pass,
    name,
    vxlan_id,
    iface,
    local_ip,
    remote_ip
):
    
    log_message("========== START VXLAN SETUP ==========")
    log_message(f"Target Device : {device_name}")
    log_message(f"VXLAN_NAME: {name}, VXLAN_ID={vxlan_id}, INTERFACE={iface},  LOCAL_IP={local_ip},  REMOTE_IP={remote_ip}")
    
    def sudo(cmd):
        log_message(f"[CMD] sudo **** | {cmd}")
        return f"echo '{device_pass}' | sudo -S {cmd}"
    
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
            
            log_message("[STEP 1] Cleanup any existing objects")
            executor.execute(sudo(f"ip link del {name} 2>/dev/null || true"))

            # Create VXLAN
            log_message(f"[STEP 2] Creating {name}")
            cmd = sudo(
                f"ip link add {name} type vxlan id {vxlan_id} "
                f"local {local_ip} remote {remote_ip} "
                f"dstport 4789 dev {iface}"
            )

            res = executor.execute(cmd)
            if res.failed:
                raise AssertionError(
                    f"VxLAN tunnel creation failed\nstdout:{res.stdout}\nstderr:{res.stderr}"
                )

            log_message(f"[OK] Tunnel {name} created successfully")

            log_message(f"========== VxLAN SETUP COMPLETE FOR {device_name}<->{name} ==========")
            time.sleep(2)
            return 0

    except Exception as e:
        log_message("========== VxLAN SETUP FAILED ==========")
        log_message(f"Exception: {type(e).__name__}")
        log_message(str(e))
        log_message(traceback.format_exc())
        raise AssertionError(f"VxLAN setup failed on {device_name}: {e}")
    
    
# =============================
# SET UP BRIDGE VXLAN TUNNEL
# =============================
@keyword("ATTACH VXLANS TO BRIDGE ON BB")
def attach_vxlans_to_bridge_bb(
    device_name,
    br_name="br-vxlan",
    tunnel_ip=None,
    stp_enable=True
):
    log_message("========== START ATTACH VXLAN BRIDGE ==========")
    log_message(f"Target Device : {device_name}")
    log_message(f"Bridge: {br_name}  STP: {stp_enable}")
    if tunnel_ip:
        log_message(f"Overlay IP: {tunnel_ip}")
    
    executor = get_registered_executor(device_name)    

    try:
        
            # ---- detect vxlan ----
            detect_cmd = r"ip -o link show | awk -F': ' '{print $2}' | grep '^vxlan' || true"
            log_message(f"[CMD] {detect_cmd}")
            res = executor.execute(detect_cmd)
            vxlan_list = res.stdout.strip().splitlines()

            if not vxlan_list:
                log_message("[FAIL] No VXLAN interfaces detected on DUT")
                raise AssertionError("No VXLAN interfaces detected on DUT")

            log_message(f"[INFO] VXLAN Interfaces detected: {vxlan_list}")

            # ---- create bridge ----
            cmd = (f"ip link add name {br_name} type bridge 2>/dev/null || true")
            log_message(f"[CMD] {cmd}")
            executor.execute(cmd)

            # ---- enable STP ----
            if stp_enable:
                cmd = (f"brctl stp {br_name} on 2>/dev/null || true")
                log_message(f"[CMD] {cmd}")
                executor.execute(cmd)

            # ---- bring up bridge ----
            cmd = (f"ip link set {br_name} up")
            log_message(f"[CMD] {cmd}")
            res = executor.execute(cmd)
            if res.failed:
                raise AssertionError(f"Failed to bring {br_name} up: {res.stderr}")

            # ---- attach VXLANS ----
            log_message("[STEP 4] Attaching VXLAN interfaces to bridge")
            for vx in vxlan_list:
                cmd = (f"ip link set {vx} master {br_name} 2>/dev/null || true")
                log_message(f"[CMD] {cmd}")
                res = executor.execute(cmd)
                if res.failed:
                    raise AssertionError(f"Failed attaching {vx} to {br_name}: {res.stderr}")

                cmd = (f"ip link set {vx} up")
                log_message(f"[CMD] {cmd}")
                executor.execute(cmd)

            # ---- overlay IP ----
            if tunnel_ip:
                log_message("[STEP 5] Assigning overlay IP")
                cmd = (f"ip addr replace {tunnel_ip}/24 dev {br_name}")
                log_message(f"[CMD] {cmd}")
                res = executor.execute(cmd)
                if res.failed:
                    raise AssertionError(f"Failed assigning overlay IP {tunnel_ip}: {res.stderr}")

                log_message(f"[PASS] Overlay IP added {tunnel_ip}")

            log_message("[PASS] VXLANs successfully attached to bridge")
            log_message("========== ATTACH COMPLETE ==========")
            return 0

    except Exception as e:
        log_message("========== ATTACH VXLAN FAILED ==========")
        log_message(f"Exception: {type(e).__name__} - {str(e)}")
        log_message(traceback.format_exc())
        raise AssertionError(
            f"VXLAN attach failed on {device_name}: {str(e)}"
        )

    
@keyword("ATTACH VXLANS TO BRIDGE ON DC")
def attach_vxlans_to_bridge_dc(
        device_name,
        device_pass,
        br_name="br-vxlan",
        tunnel_ip=None,
        stp_enable=True
    ):
    
    log_message("========== START ATTACH VXLAN BRIDGE ==========")
    log_message(f"Target Device : {device_name}")
    log_message(f"Bridge: {br_name}  STP: {stp_enable}")
    if tunnel_ip:
        log_message(f"Overlay IP: {tunnel_ip}")

    def sudo(cmd):
        log_message(f"[CMD] sudo **** | {cmd}")
        return f"echo '{device_pass}' | sudo -S {cmd}"
    
    executor = get_registered_executor(device_name)

    try: 
            # detect vxlan
            detect_cmd = sudo(
                r"ip -o link show | awk -F': ' '{print $2}' | grep '^vxlan' || true"
            )
            res = executor.execute(detect_cmd)
            vxlan_list = res.stdout.strip().splitlines()

            if not vxlan_list:
                log_message("[FAIL] No VXLAN interfaces detected on DUT")
                raise AssertionError("No VXLAN interfaces detected on DUT")

            log_message(f"[INFO] VXLAN Interfaces detected: {vxlan_list}")

            # create bridge
            cmd = sudo(f"ip link add name {br_name} type bridge 2>/dev/null || true")
            executor.execute(cmd)
            
            # enable stp
            if stp_enable:
                cmd = sudo(f"brctl stp {br_name} on 2>/dev/null || true")
                log_message(f"[CMD] {cmd}")
                executor.execute(cmd)

            # bring up bridge
            cmd = sudo(f"ip link set {br_name} up")
            res = executor.execute(cmd)
            if res.failed:
                raise AssertionError(f"Failed to bring {br_name} up: {res.stderr}")

            # attach vxlans
            log_message("[STEP 4] Attaching VXLAN interfaces to bridge")
            for vx in vxlan_list:
                cmd = sudo(f"ip link set {vx} master {br_name} 2>/dev/null || true")
                res = executor.execute(cmd)
                if res.failed:
                    raise AssertionError(f"Failed attaching {vx} to {br_name}: {res.stderr}")

                cmd = sudo(f"ip link set {vx} up")
                executor.execute(cmd)

            # overlay IP
            if tunnel_ip:
                log_message("[STEP 5] Assigning overlay IP")
                cmd = sudo(f"ip addr replace {tunnel_ip}/24 dev {br_name}")
                log_message(f"[CMD] {cmd}")
                res = executor.execute(cmd)
                if res.failed:
                    raise AssertionError(f"Failed assigning overlay IP {tunnel_ip}: {res.stderr}")

                log_message(f"[PASS] Overlay IP added {tunnel_ip}")

            log_message("[PASS] VXLANs successfully attached to bridge")
            log_message("========== ATTACH COMPLETE ==========")
            return 0

    except Exception as e:
        log_message("========== ATTACH VXLAN FAILED ==========")
        log_message(f"Exception: {type(e).__name__} - {str(e)}")
        log_message(traceback.format_exc())
        raise AssertionError(
            f"VXLAN attach failed on {device_name}: {str(e)}"
        )

    
# =============================
# VERIFY VXLAN REDUNDANCY
# =============================
@keyword("VERIFY VXLAN REDUNDANCY ON BB")
def verify_vxlan_redundancy_bb(
        device_name,
        vxlan_a_name, vxlan_b_name,
        target_overlay_ip,
        ping_interval=1,
        iface_timeout=60
    ):
    log_message("========== START VXLAN REDUNDANCY VERIFICATION ON BB ==========")
    log_message(f"Target Device : {device_name}")
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
            log_message("[TEST 1] Bringing VXLAN-A DOWN")
            pre_time = ping_state["last_success"]
            run(f"ip link set {vxlan_a_name} down", executor)

            log_message("[TEST 1] Waiting recovery")
            fail_start = time.time()
            while time.time() - fail_start <= iface_timeout:
                if ping_state["last_success"] > pre_time:
                    break
                time.sleep(0.2)
            else:
                run(f"ip link set {vxlan_a_name} up", executor)
                ping_state["stop"] = True
                ping_thread_ref.join()
                raise AssertionError("VXLAN-A failover failed — no ping recovered")

            run(f"ip link set {vxlan_a_name} up", executor)
            time.sleep(2)

            # TEST2 — B DOWN
            log_message("[TEST 2] Bringing VXLAN-B DOWN")
            pre_time = ping_state["last_success"]
            run(f"ip link set {vxlan_b_name} down", executor)

            log_message("[TEST 2] Waiting recovery")
            fail_start = time.time()
            while time.time() - fail_start <= iface_timeout:
                if ping_state["last_success"] > pre_time:
                    break
                time.sleep(0.2)
            else:
                run(f"ip link set {vxlan_b_name} up", executor)
                ping_state["stop"] = True
                ping_thread_ref.join()
                raise AssertionError("VXLAN-B failover failed — no ping recovered")

            run(f"ip link set {vxlan_b_name} up", executor)
            time.sleep(2)

            ping_state["stop"] = True
            ping_thread_ref.join()
            log_message("========== VXLAN REDUNDANCY TEST PASSED ==========")

    except Exception as ex:
        ping_state["stop"] = True
        if ping_thread_ref:
            ping_thread_ref.join()
        raise AssertionError(
            f"VXLAN redundancy verification failed: {str(ex)}"
        )

#############SUDO AND PASSWORD##############
@keyword("VERIFY VXLAN REDUNDANCY ON DC")
def verify_vxlan_redundancy_dc(
        device_name,  device_pass,
        vxlan_a_name, vxlan_b_name,
        target_overlay_ip,
        ping_interval=1,
        iface_timeout=60
    ):
    log_message("========== START VxLAN REDUNDANCY VERIFICATION ON DC ==========")
    log_message(f"Target Device : {device_name}")
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
            log_message("[TEST 1] Bringing VXLAN-A DOWN")
            pre_time = ping_state["last_success"]
            run(f"ip link set {vxlan_a_name} down", executor)

            log_message("[TEST 1] Waiting recovery")
            fail_start = time.time()
            while time.time() - fail_start <= iface_timeout:
                if ping_state["last_success"] > pre_time:
                    break
                time.sleep(0.2)
            else:
                run(f"ip link set {vxlan_a_name} up", executor)
                ping_state["stop"] = True
                ping_thread_ref.join()
                raise AssertionError("VXALN-A failover failed — no ping recovered")

            run(f"ip link set {vxlan_a_name} up", executor)
            time.sleep(2)

            # TEST2 — B DOWN
            log_message("[TEST 2] Bringing VXLAN-B DOWN")
            pre_time = ping_state["last_success"]
            run(f"ip link set {vxlan_b_name} down", executor)

            log_message("[TEST 2] Waiting recovery")
            fail_start = time.time()
            while time.time() - fail_start <= iface_timeout:
                if ping_state["last_success"] > pre_time:
                    break
                time.sleep(0.2)
            else:
                run(f"ip link set {vxlan_b_name} up", executor)
                ping_state["stop"] = True
                ping_thread_ref.join()
                raise AssertionError("VXLAN-B failover failed — no ping recovered")

            run(f"ip link set {vxlan_b_name} up", executor)
            time.sleep(2)

            ping_state["stop"] = True
            ping_thread_ref.join()
            log_message("========== VXLAN REDUNDANCY TEST PASSED ==========")

    except Exception as ex:
        ping_state["stop"] = True
        if ping_thread_ref:
            ping_thread_ref.join()
        raise AssertionError(
            f"VXLAN redundancy verification failed: {str(ex)}"
        )        

# =============================
# TEARDOWN VXLAN TUNNEL
# =============================
@keyword("TEARDOWN VXLAN AND BRIDGE")
def teardown_vxlan_and_bridge(
    device_name,
    device_pass,
    vxlan_name,
    bridge_name
):
    log_message("========== START VXLAN + BRIDGE TEARDOWN ==========")
    log_message(f"Target Device : {device_name}")
    log_message(f"VXLAN         : {vxlan_name}")
    log_message(f"BRIDGE        : {bridge_name}")

    executor = get_registered_executor(device_name)

    def sudo(cmd):
        log_message(f"[CMD] sudo **** | {cmd}")
        return f"echo '{device_pass}' | sudo -S {cmd}"

    try:
        # ---------------- OS DETECTION ----------------
        os_info = executor.execute(
            "cat /etc/os-release 2>/dev/null || true"
        ).stdout.lower()
        is_openwrt = "openwrt" in os_info

        # ---------------- STEP 1: Delete VXLAN ----------------
        log_message("[STEP 1] Deleting VXLAN interface")
        vxlan_cmd = f"ip link del {vxlan_name} 2>/dev/null || true"
        if is_openwrt:
            log_message(f"[CMD] {vxlan_cmd}")
            res = executor.execute(vxlan_cmd)
        else:
            res = executor.execute(sudo(vxlan_cmd))

        if res.failed:
            raise AssertionError(
                f"Failed deleting VXLAN {vxlan_name}\n"
                f"stdout: {res.stdout}\n"
                f"stderr: {res.stderr}"
            )

        # ---------------- STEP 2: Delete Bridge ----------------
        log_message("[STEP 2] Deleting bridge")
        bridge_cmd=  f"ip link del {bridge_name} 2>/dev/null || true"
        if is_openwrt:
            log_message(f"[CMD] {vxlan_cmd}")
            res = executor.execute(bridge_cmd)
        else:
            res = executor.execute(sudo(bridge_cmd))

        if res.failed:
            raise AssertionError(
                f"Failed deleting bridge {bridge_name}\n"
                f"stdout: {res.stdout}\n"
                f"stderr: {res.stderr}"
            )

        log_message("========== VXLAN + BRIDGE TEARDOWN COMPLETE ==========")
        return 0

    except Exception as e:
        log_message("========== VXLAN + BRIDGE TEARDOWN FAILED ==========")
        log_message(f"Exception: {type(e).__name__}")
        log_message(str(e))
        log_message(traceback.format_exc())
        return False

