# START_DESCRIPTION

#1.Connect to the DUT and PC devices.
#2.Check if any VRF is present on the DUT.
#3.Remove the VRF from the DUT.
#4.Restart the FRR service on the DUT.
#5.Check if any VRF is present on the PC.
#6.Remove the VRF from the PC.
#7.Restart the FRR service on the PC.
#8.Confirm that the VRF is completely removed from both devices.

# END_DESCRIPTION

import os
import time
from datetime import datetime
from robot.api.deco import keyword
from robot.libraries.BuiltIn import BuiltIn
from execution.executor_helper import get_registered_executor


# =================================================
# Log setup (UNCHANGED PATTERN)
# =================================================
LOG_FOLDER = os.path.join(os.path.dirname(__file__), '..', '..', 'logs')
os.makedirs(LOG_FOLDER, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE_PATH = os.path.join(LOG_FOLDER, f"custom_log_{timestamp}.log")


# =================================================
# Logging Helpers
# =================================================
def log_message(message: str):
    ts = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    BuiltIn().log_to_console(ts)
    with open(LOG_FILE_PATH, "a") as f:
        f.write(ts + "\n")


@keyword("Initialize Custom Log File")
def initialize_custom_log_file():
    log_message("[STEP] Custom log initialized")


@keyword("Log Message To Custom File")
def log_message_to_custom_file(message: str):
    log_message(message)


def log(msg):
    try:
        BuiltIn().run_keyword("Log Message To Custom File", msg)
    except Exception:
        log_message(msg)


# =================================================
# SSH / Executor Helpers
# =================================================
def get_executor(device_name):
    executor = get_registered_executor(device_name)
    if not executor:
        raise RuntimeError(f"No executor registered for device '{device_name}'")
    return executor


def run_cmd(device_name, cmd):
    executor = get_executor(device_name)
    log(f"[{device_name}] $ {cmd}")
    result = executor.execute(cmd)

    stdout = result.stdout.strip() if result.stdout else ""
    stderr = result.stderr.strip() if hasattr(result, "stderr") and result.stderr else ""

    if stdout:
        log(f"[{device_name}] STDOUT:\n{stdout}")
    else:
        log(f"[{device_name}] STDOUT: <empty>")

    if stderr:
        log(f"[{device_name}] STDERR:\n{stderr}")

    return result

#
# # =================================================
# # VRF TEARDOWN (ROLE AWARE)
# # =================================================
# @keyword("Teardown Vrf")
# def teardown_vrf(device, cfg):
#     """
#     cfg example:
#     {
#         "interface": "br-lan",
#         "role": "NXP" | "RPI"
#     }
#     """
#
#     # role = cfg.get("role", "NXP").upper()
#     log_message(f"--- VRF teardown started on {device}")
#
#     # STEP 1: Detach interface from VRF
#     iface = cfg.get("interface")
#     if iface:
#         run_cmd(device, f"ip link set {iface} nomaster || true")       # || true chewck and remove
#         run_cmd(device, f"ip addr flush dev {iface} || true")
#     else:
#         log_message(f"[{device}] No interface provided, skipping interface cleanup")
#
#     # STEP 2: Delete VRF (NO vrf down)
#     run_cmd(device, "ip link del vrf1 || true")
#
#     log_message(f"--- VRF teardown completed on {device} ---")


@keyword("Teardown Vrf")
def teardown_vrf(device, cfg):

    log_message(f"--- VRF teardown started on {device}")

    # Get all VRFs
    result = run_cmd(device, "ip -br link show type vrf || true")
    vrf_output = result.stdout.strip()

    if not vrf_output:
        log_message(f"[{device}] No VRFs present")
        return

    for line in vrf_output.splitlines():
        vrf_name = line.split()[0]
        log_message(f"[{device}] Removing VRF: {vrf_name}")

        # Detach interfaces
        iface_result = run_cmd(device, f"ip link show master {vrf_name} || true")
        for iface_line in iface_result.stdout.splitlines():
            parts = iface_line.strip().split(":")
            if len(parts) > 1:
                iface = parts[1].strip().split("@")[0]
                log_message(f"[{device}] Detaching {iface}")
                run_cmd(device, f"ip link set {iface} nomaster || true")

        # # Bring down and delete
        # run_cmd(device, f"ip link set {vrf_name} down || true")
        # run_cmd(device, f"ip link del {vrf_name} || true")

        # Decide command prefix
        cmd_prefix = "sudo " if device == "PC" else ""

        # Bring down VRF
        run_cmd(device, f"{cmd_prefix}ip link set {vrf_name} down || true")

        # Delete VRF
        run_cmd(device, f"{cmd_prefix}ip link del {vrf_name} || true")

    log_message(f"--- VRF teardown completed on {device} ---")
# =================================================
# FRR RESTART (ROLE AWARE)
# =================================================
@keyword("Restart Frr")
def restart_frr(device):
    log_message(f"Restarting FRR on {device}")

    # Works for both NXP and RPi safely
    run_cmd(device, "systemctl restart frr || service frr restart || true")
    #time.sleep(5)

#
# # =================================================
# # VALIDATION
# # =================================================
# @keyword("Validate Vrf Removed")
# def validate_vrf_removed(device):
#     res = run_cmd(device, "ip -br link show type vrf || true")
#
#     if res.stdout and "vrf" in res.stdout.lower():
#         raise AssertionError(f"VRF still present on {device}")
#
#     log_message(f"VRF successfully removed on {device}")

@keyword("Validate Vrf Removed")
def validate_vrf_removed(device):
    res = run_cmd(device, "ip -br link show type vrf || true")

    if res.stdout.strip():
        raise AssertionError(f"VRF still present on {device}: {res.stdout}")

    log_message(f"VRF successfully removed on {device}")
