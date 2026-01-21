import time
from robot.api.deco import keyword
from robot.libraries.BuiltIn import BuiltIn
from SSHHelper import SSHConnection

PING_IP = None

def _log(msg):
    """Log to console and custom file."""
    BuiltIn().log_to_console(msg)
    BuiltIn().run_keyword("Log Message To Custom File", msg)

@keyword
def set_ping_ip(ip):
    global PING_IP
    PING_IP = ip
    _log(f"[INFO] Using PING_IP = {PING_IP}")

# =====================================================================
# INTERNAL FIREWALL FUNCTIONS (use SSHConnection directly)
# =====================================================================

def _add_firewall_rule(ssh: SSHConnection, rule_name, target):
    # Step 1: Create rule skeleton
    res = ssh.execute("uci add firewall rule")
    _log(f"Added firewall rule → {res.stdout}\nError: {res.stderr}")

    # Step 2: Determine last created section
    res = ssh.execute("uci show firewall | tail -n 1")
    last = res.stdout.strip()
    section = last.split('=')[0].split('.')[1] if '=' in last else f"{rule_name}_tmp"

    # Step 3: Apply rule parameters
    cmds = [
        f"uci set firewall.{section}.name='{rule_name}'",
        f"uci set firewall.{section}.src='lan'",
        f"uci set firewall.{section}.proto='icmp'",
        f"uci set firewall.{section}.icmp_type='echo-request'",
        f"uci set firewall.{section}.target='{target}'",
        f"uci set firewall.{section}.enabled='1'",
        f"uci set firewall.{section}.family='ipv4'"
    ]

    for cmd in cmds:
        res = ssh.execute(cmd)
        _log(f"Executed: {cmd}\nOutput: {res.stdout}\nError: {res.stderr}")

    ssh.execute("uci commit firewall")
    ssh.execute("/etc/init.d/firewall restart")
    time.sleep(1)

# =====================================================================
# PUBLIC KEYWORDS (Robot Framework)
# =====================================================================

@keyword
def add_allow_ping_rule(openwrt_ip, user="root", password="root"):
    ssh = SSHConnection(openwrt_ip, user, password).connect()
    _add_firewall_rule(ssh, "Allow-Ping", "ACCEPT")
    ssh.disconnect()

@keyword
def add_block_ping_rule(openwrt_ip, user="root", password="root"):
    ssh = SSHConnection(openwrt_ip, user, password).connect()
    _add_firewall_rule(ssh, "Block-Ping", "REJECT")
    ssh.disconnect()

@keyword
def delete_allow_ping_rules(openwrt_ip, user="root", password="root"):
    ssh = SSHConnection(openwrt_ip, user, password).connect()

    res = ssh.execute("uci show firewall | grep 'Allow-Ping\\|Block-Ping'")
    matching = []
    for line in res.stdout.splitlines():
        if '=' in line:
            section = line.split('=')[0].split('.')[1]
            matching.append(section)

    for section in reversed(matching):
        res2 = ssh.execute(f"uci delete firewall.{section}")
        _log(f"Deleted rule → uci delete firewall.{section}\nOutput: {res2.stdout}\nError: {res2.stderr}")

    ssh.execute("uci commit firewall")
    ssh.execute("/etc/init.d/firewall restart")

    ssh.disconnect()
    time.sleep(1)

@keyword
def verify_ping_success(src_ip, user, password):
    if not PING_IP:
        raise AssertionError("PING_IP not set before calling verify_ping_success.")

    ssh = SSHConnection(src_ip, user, password).connect()
    res = ssh.execute(f"ping -c 3 {PING_IP}")
    ssh.disconnect()

    _log(f"Ping output:\n{res.stdout}")

    if "bytes from" not in res.stdout:
        raise AssertionError(f"Ping to {PING_IP} FAILED. Expected SUCCESS.")

@keyword
def verify_ping_failure(src_ip, user, password):
    if not PING_IP:
        raise AssertionError("PING_IP not set before calling verify_ping_failure.")

    ssh = SSHConnection(src_ip, user, password).connect()
    res = ssh.execute(f"ping -c 3 {PING_IP}")
    ssh.disconnect()

    _log(f"Ping output:\n{res.stdout}")

    if (
        "Destination Host Unreachable" not in res.stdout
        and "100% packet loss" not in res.stdout
        and "Destination Port Unreachable" not in res.stdout
    ):
        raise AssertionError(f"Ping to {PING_IP} unexpectedly SUCCEEDED. Expected FAILURE.")
