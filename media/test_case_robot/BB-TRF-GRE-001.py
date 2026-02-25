# START_DESCRIPTION 
 
# 1. Configure GRE tunnel on the Black Box with remote endpoint IP and local interface IP.
# 2. Establish the GRE tunnel from Black Box to remote GRE endpoint.
# 3. Verify tunnel status on both Black Box and remote endpoint (ip tunnel show).                                                                                          
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
# SET UP GRE TUNNEL
# =============================
@keyword("SET UP GRE TUNNEL")
def setup_gre_tunnel(
    device_name,
    tunnel_name,
    underlay_iface,
    local_ip,
    remote_ip,
    overlay_ip
):
    log_message(f"========== START GRE SETUP ON {device_name} ==========")
    log_message(f"Target Device: {device_name}")
    log_message(f"GRE Tunnel: {tunnel_name}")
    log_message(f"Local → Remote: {local_ip} → {remote_ip}")
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
        log_message("[STEP 1] Cleaning up old GRE interface")
        executor.execute(f"ip link set {tunnel_name} down 2>/dev/null || true")
        executor.execute(f"ip link del {tunnel_name} 2>/dev/null || true")

        # STEP 2: Create GRE
        log_message("[STEP 2] Creating GRE tunnel")
        create_cmd = (
                f"ip tunnel add {tunnel_name} mode gre "
                f"remote {remote_ip} local {local_ip} ttl 255 dev {underlay_iface}"
        )
        log_message(f"[CMD] {create_cmd}")
        result = executor.execute(create_cmd)

        if result.failed:
                raise AssertionError(
                    f"GRE tunnel creation failed on RPI {device_name}\n"
                    f"stdout: {result.stdout}\n"
                    f"stderr: {result.stderr}"
                )

            # STEP 3: Bring interface up
        log_message("[STEP 3] Bringing GRE interface UP")
        result = executor.execute(f"ip link set {tunnel_name} up")

        if result.failed:
                raise AssertionError(
                    f"Failed to bring GRE interface {tunnel_name} UP on {device_name}"
                )
            # STEP 4: Assign overlay IP
        log_message(f"[STEP 4] Assigning IP {overlay_ip}/30 to {tunnel_name}")
        executor.execute(f"ip addr flush dev {tunnel_name}")
        result = executor.execute(f"ip addr add {overlay_ip}/30 dev {tunnel_name}")

        if result.failed:
                raise AssertionError(f"Failed to assign IP {overlay_ip}/24 to {tunnel_name}")
       
            
        log_message(f"========== GRE SETUP COMPLETE ON {device_name} ==========")
        return 0

    except AssertionError:
        log_message("========== GRE SETUP FAILED (ASSERTION) ==========")
        raise

    except Exception as e:
        log_message("========== GRE SETUP FAILED (EXCEPTION) ==========")
        raise AssertionError(
            f"Unexpected error during GRE setup \n"
            f"{type(e).__name__}: {str(e)}\n"
            f"Traceback:\n{traceback.format_exc()}"
        )



@keyword("SET UP GRE TUNNEL ON RPI")
def setup_gre_tunnel_rpi( 
        pc_name,
        pc_pass,
        tunnel_name,
        underlay_iface,
        local_ip,
        remote_ip,
        overlay_ip
):  
    log_message(f"========== START GRE SETUP ON {pc_name} ==========")
    log_message(f"Target Device: {pc_name}")
    log_message(f"GRE Tunnel: {tunnel_name}")
    log_message(f"Local → Remote: {local_ip} → {remote_ip}")
    log_message(f"Tunnel IP: {overlay_ip}")
    
    def sudo(cmd):
        log_message(f"[CMD] sudo **** | {cmd}")
        return f"echo '{pc_pass}' | sudo -S {cmd}"

    executor = get_registered_executor(pc_name)
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
        log_message("[STEP 1] Cleaning up old GRE interface")
        executor.execute(sudo(f"ip link set {tunnel_name} down 2>/dev/null || true"))
        executor.execute(sudo(f"ip link del {tunnel_name} 2>/dev/null || true"))

        # STEP 2: Create GRE
        log_message("[STEP 2] Creating GRE tunnel")
        create_cmd = sudo(
                    f"ip tunnel add {tunnel_name} mode gre "
                    f"remote {remote_ip} local {local_ip} ttl 255 dev {underlay_iface}"
                )
        result = executor.execute(create_cmd)
        if result.failed:
                raise AssertionError(
                    f"GRE tunnel creation failed on RPI {pc_name}\n"
                    f"stdout: {result.stdout}\n"
                    f"stderr: {result.stderr}"
                )

            # STEP 3: Bring UP
        log_message("[STEP 3] Bringing GRE interface UP")
        result = executor.execute(sudo(f"ip link set {tunnel_name} up"))

        if result.failed:
                raise AssertionError(
                    f"Failed to bring GRE interface {tunnel_name} UP on RPI"
                )

        # STEP 4: Assign IP
        log_message(f"[STEP 4] Assigning IP {overlay_ip}/30 to {tunnel_name}")
        executor.execute(sudo(f"ip addr flush dev {tunnel_name}"))
        result = executor.execute( sudo(f"ip addr add {overlay_ip}/30 dev {tunnel_name}"))
       
        if result.failed:
                raise AssertionError(f"Failed to assign IP {overlay_ip}/24 to {tunnel_name}")
   
          
        log_message(f"========== GRE SETUP COMPLETE ON {pc_name} ==========")
        return 0
    except AssertionError:
        log_message("========== GRE SETUP FAILED (ASSERTION) ==========")
        raise

    except Exception as e:
        log_message("========== GRE SETUP FAILED (EXCEPTION) ==========")
        raise AssertionError(
            f"Unexpected error during GRE setup on RPI {pc_name}\n"
            f"{type(e).__name__}: {str(e)}\n"
            f"Traceback:\n{traceback.format_exc()}"
        )


    
            
@keyword("VERIFY GRE TUNNEL")
def verify_gre_tunnel(
    protocol,capture_node_name, capture_node_pass,ping_node_name,
    capture_node_iface, capture_node_outer_ip, ping_node_outer_ip,
    capture_node_inner_ip, ping_node_inner_ip
):
 
    capture_node_executor= get_registered_executor(capture_node_name)
    ping_node_executor= get_registered_executor(ping_node_name)
    
    log_message("[STEP] Starting GRE tunnel verification")
    log_message(f"[INFO] Capture Node : {capture_node_name}")
    log_message(f"[INFO] Ping Node    : {ping_node_name}")
    log_message(f"[INFO] Underlay IF  : {capture_node_iface}")
    log_message(f"[INFO] OUTER IPs    : {capture_node_outer_ip} <-> {ping_node_outer_ip}")
    log_message(f"[INFO] INNER IPs    : {capture_node_inner_ip} <-> {ping_node_inner_ip}")
   

    pcap_file = "/tmp/gre_capture.pcap"
    temp_file = "/tmp/ping_res.txt"

    try:
        def sudo(cmd):
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
                time.sleep(1)
                cmd = f"ping -c 5 {capture_node_inner_ip}"
                log_message(f"[PING] {cmd}")
                result = ping_node_executor.execute(cmd)

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
                    # ===== MQTT SAFE MODE =====
                    log_message("[TCPDUMP] MQTT mode → background capture")

                    # Cleanup
                    capture_node_executor.execute(f"rm -f {pcap_file} 2>/dev/null || true")

                    # Start tcpdump in background
                    if is_openwrt:
                        # start_cmd = (f"tcpdump -i {capture_node_iface} "f"-nn ip proto 47 -w {pcap_file} & echo $!")
                        start_cmd = (f"tcpdump -i any -nn -U -c 10 ip proto 47 -w {pcap_file} > /dev/null 2>&1 & echo $!")
                    else:
                        # start_cmd = sudo(f"tcpdump -i {capture_node_iface} "f"-nn ip proto 47 -w {pcap_file} & echo $!")
                        start_cmd = sudo(f"tcpdump -i any -nn -U -c 10 ip proto 47 -w {pcap_file} > /dev/null 2>&1 & echo $!")

                    log_message(f"[TCPDUMP-MQTT-START] {start_cmd}")
                    pid_result = capture_node_executor.execute(start_cmd)
                    tcpdump_pid = pid_result.stdout.strip()

                    # Allow ping + traffic
                    time.sleep(8)

                    # Stop tcpdump
                    capture_node_executor.execute(
                        f"kill -INT {tcpdump_pid} 2>/dev/null || true"
                    )

                    # Read capture
                    read_cmd = f"tcpdump -nn -vv -r {pcap_file}"
                    result = capture_node_executor.execute(read_cmd)

                else:
                    # ===== SSH LIVE MODE =====
                    log_message("[TCPDUMP] SSH mode → live capture")

                    if is_openwrt:
                        # cmd = (f"tcpdump -i {capture_node_iface} "f"-nn -vv -c 10 ip proto 47")
                        cmd = (f"tcpdump -i any -nn -vv -c 10 ip proto 47")
                    else:
                        # cmd = sudo(f"tcpdump -i {capture_node_iface} "f"-nn -vv -c 10 ip proto 47")
                        cmd = sudo(f"tcpdump -i ant -nn -vv -c 10 ip proto 47")

                    log_message(f"[TCPDUMP-SSH] {cmd}")
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
        t2.start()

        t1.join()
        t2.join()

        # ---------------- OUTPUT ----------------
        log_message("[OUTPUT] ===== TCPDUMP =====")
        log_message(tcpdump_output["stdout"])
        log_message("[OUTPUT] ===== PING =====")
        log_message(ping_output["stdout"])

        # ---------------- VALIDATION ----------------
        if tcpdump_output["failed"]:
            raise AssertionError("tcpdump failed — cannot validate GRE")

        tcpdump_lines = tcpdump_output["stdout"].splitlines()

        # ---- GRE HEADER ----
        if not any("GRE" in l for l in tcpdump_lines):
            raise AssertionError("GRE header not detected in tcpdump")
        log_message("[OK] GRE header detected")

        # ---- OUTER IP CHECK ----
        outer_forward = f"{ping_node_outer_ip} > {capture_node_outer_ip}"
        outer_reverse = f"{capture_node_outer_ip} > {ping_node_outer_ip}"

        outer_fwd_hits = [l for l in tcpdump_lines if outer_forward in l]
        outer_rev_hits = [l for l in tcpdump_lines if outer_reverse in l]

        if not outer_fwd_hits:
            raise AssertionError("OUTER forward GRE traffic missing")
        log_message("[OK] GRE forward OUTER encapsulation detected")
        for l in outer_fwd_hits:
            log_message(f"[MATCH]     {l}")

        if not outer_rev_hits:
            raise AssertionError("OUTER reverse GRE traffic missing")
        log_message("[OK] GRE reverse OUTER encapsulation detected")
        for l in outer_rev_hits:
            log_message(f"[MATCH]     {l}")

        # ---- INNER ICMP (BEST EFFORT LOGGING) ----
        inner_forward = f"{ping_node_inner_ip} > {capture_node_inner_ip}: ICMP"
        inner_reverse = f"{capture_node_inner_ip} > {ping_node_inner_ip}: ICMP"

        inner_fwd_hits = [l for l in tcpdump_lines if inner_forward in l]
        inner_rev_hits = [l for l in tcpdump_lines if inner_reverse in l]

        if inner_fwd_hits:
            log_message("[OK] INNER forward ICMP packets observed")
            for l in inner_fwd_hits:
                log_message(f"[MATCH]     {l}")
        else:
            log_message("[WARN] INNER forward ICMP not explicitly seen")

        if inner_rev_hits:
            log_message("[OK] INNER reverse ICMP packets observed")
            for l in inner_rev_hits:
                log_message(f"[MATCH]     {l}")
        else:
            log_message("[WARN] INNER reverse ICMP not explicitly seen")
        
        # ---- PING CHECK ----
        # if ping_output["failed"]:
        #     raise AssertionError("Ping execution failed")

        # if "0% packet loss" not in ping_output["stdout"]:
        #     raise AssertionError("Ping packet loss detected")

        log_message("[SUCCESS] GRE tunnel verification PASSED")
        return True

    finally:
        # Cleanup
        capture_node_executor.execute(f"rm -f {pcap_file} 2>/dev/null || true")
        ping_node_executor.execute(f"rm -f {temp_file}")


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
   