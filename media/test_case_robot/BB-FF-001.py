# START_DESCRIPTION
# 1. Set the target PING_IP for firewall verification.
# 2. Add firewall rule to allow ICMP echo-request (ping) traffic.
# 3. Commit firewall configuration and restart firewall service.
# 4. From PC, verify ping to router succeeds.
# 5. Modify firewall rule to block ICMP echo-request traffic.
# 6. Commit firewall configuration and restart firewall service.
# 7. From PC, verify ping to router fails (100% packet loss expected).
# 8. Delete custom firewall rules and restore default configuration.
# 9. If ping behavior matches rule configuration, mark test as PASSED.
# END_DESCRIPTION

import os
import traceback
from datetime import datetime
from robot.api.deco import keyword
from robot.libraries.BuiltIn import BuiltIn
from execution.executor_helper import get_registered_executor

LOG_FOLDER = os.path.join(os.path.dirname(__file__), '..', '..', 'logs')
os.makedirs(LOG_FOLDER, exist_ok=True)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE_PATH = os.path.join(LOG_FOLDER, f"custom_log_{timestamp}.log")


def log_message(message: str):
    timestamped = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    BuiltIn().log_to_console(timestamped)
    with open(LOG_FILE_PATH, "a") as log_file:
        log_file.write(timestamped + "\n")


@keyword("Initialize Custom Log File")
def initialize_custom_log_file():
    log_message("[STEP] Custom log initialized")


@keyword("Log Message To Custom File")
def log_message_to_custom_file(message: str):
    log_message(message)


PING_IP = None


@keyword("Set Ping Ip")
def set_ping_ip(ip):
    global PING_IP
    PING_IP = ip
    log_message(f"[STEP] Set PING_IP = {PING_IP}")


@keyword("Add Allow Ping Rule")
def add_allow_ping_rule(dut_name):
    executor = get_registered_executor(dut_name)
    section = "Allow_Ping_ANY"

    executor.execute("uci delete firewall.Block_Ping_ANY")
    executor.execute(f"uci delete firewall.{section}")

    cmds = [
        f"uci set firewall.{section}=rule",
        f"uci set firewall.{section}.name='Allow-Ping-to-Router'",
        f"uci set firewall.{section}.src='*'",
        f"uci set firewall.{section}.proto='icmp'",
        f"uci set firewall.{section}.icmp_type='echo-request'",
        f"uci set firewall.{section}.target='ACCEPT'",
        f"uci set firewall.{section}.enabled='1'",
        f"uci set firewall.{section}.family='ipv4'",
    ]

    for cmd in cmds:
        res = executor.execute(cmd)
        if res.failed:
            raise AssertionError(res.stderr)

    executor.execute("uci commit firewall")
    executor.execute("/etc/init.d/firewall restart")


@keyword("Add Block Ping Rule")
def add_block_ping_rule(dut_name):
    executor = get_registered_executor(dut_name)
    section = "Block_Ping_ANY"

    executor.execute("uci delete firewall.Allow_Ping_ANY")
    executor.execute(f"uci delete firewall.{section}")

    cmds = [
        f"uci set firewall.{section}=rule",
        f"uci set firewall.{section}.name='Block-Ping-to-Router'",
        f"uci set firewall.{section}.src='*'",
        f"uci set firewall.{section}.proto='icmp'",
        f"uci set firewall.{section}.icmp_type='echo-request'",
        f"uci set firewall.{section}.target='REJECT'",
        f"uci set firewall.{section}.enabled='1'",
        f"uci set firewall.{section}.family='ipv4'",
    ]

    for cmd in cmds:
        res = executor.execute(cmd)
        if res.failed:
            raise AssertionError(res.stderr)

    executor.execute("uci commit firewall")
    executor.execute("/etc/init.d/firewall restart")


@keyword("Delete Ping Rules")
def delete_ping_rules(dut_name):
    executor = get_registered_executor(dut_name)
    executor.execute("uci delete firewall.Allow_Ping_ANY")
    executor.execute("uci delete firewall.Block_Ping_ANY")
    executor.execute("uci commit firewall")
    executor.execute("/etc/init.d/firewall restart")


@keyword("Verify Ping Success")
def verify_ping_success(pc_name):
    if not PING_IP:
        raise AssertionError("PING_IP not set")

    log_message(f"[PING TEST] Expect SUCCESS from {pc_name} → {PING_IP}")
    executor = get_registered_executor(pc_name)
    res = executor.execute(f"ping -c 4 -W 3 {PING_IP}")

    log_message("[PING OUTPUT]")
    log_message(res.stdout.strip())

    if "bytes from" not in res.stdout or "100% packet loss" in res.stdout:
        raise AssertionError(f"Ping to {PING_IP} FAILED — expected success")


@keyword("Verify Ping Failure")
def verify_ping_failure(pc_name):
    if not PING_IP:
        raise AssertionError("PING_IP not set")

    log_message(f"[PING TEST] Expect FAILURE from {pc_name} → {PING_IP}")
    executor = get_registered_executor(pc_name)
    res = executor.execute(f"ping -c 4 -W 3 {PING_IP}")

    log_message("[PING OUTPUT]")
    log_message(res.stdout.strip())

    if "100% packet loss" not in res.stdout and "bytes from" in res.stdout:
        raise AssertionError(f"Ping to {PING_IP} SUCCEEDED — expected failure")

