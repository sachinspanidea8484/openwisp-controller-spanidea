# START_DESCRIPTION
# 1. Initialize custom log file for DoS protection test.
# 2. Detect PC IP address dynamically.
# 3. Send multiple invalid SSH login attempts to BB using wrong password.
# 4. Repeat failed login attempts based on configured max_attempts.
# 5. Check dropbear.log for bad password attempt entries.
# 6. Verify if PC IP appears in fail2ban ban list.
# 7. Attempt valid SSH login after cooldown period.
# 8. Poll periodically until login is unblocked or timeout occurs.
# 9. Confirm that valid login succeeds after unblock.
# 10. Log total test duration and final status (BLOCKED / UNBLOCKED).
# END_DESCRIPTION

import os
import time
from datetime import datetime
from robot.api.deco import keyword
from robot.libraries.BuiltIn import BuiltIn
from execution.executor_helper import get_registered_executor

# ============================================================
# LOGGING SETUP
# ============================================================

LOG_FOLDER = os.path.join(os.path.dirname(__file__), "..", "..", "logs")
os.makedirs(LOG_FOLDER, exist_ok=True)

LOG_FILE_PATH = os.path.join(
    LOG_FOLDER,
    f"dos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
)


def log(message, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] [{level}] {message}"

    BuiltIn().log_to_console(line)
    BuiltIn().log(line)

    try:
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ============================================================
# COMMON KEYWORDS
# ============================================================

@keyword("Initialize Custom Log File")
def initialize_custom_log_file():
    log("========== START DOS TEST ==========", "STEP")


@keyword("Log Message To Custom File")
def log_message_to_custom_file(message):
    log(message, "INFO")


# ============================================================
# MAIN DOS TEST
# ============================================================

@keyword("Perform Dos Test")
def perform_dos_test(
    pc_name,
    bb_name,
    bb_ip,
    bb_user,
    bb_pass,
    max_attempts=5,
    cooldown_period=60,
    attempt_timeout=20
):
    test_start = time.time()
    log("===== START DoS TEST =====", "STEP")

    pc_executor = get_registered_executor(pc_name)
    bb_executor = get_registered_executor(bb_name)

    # --------------------------------------------------------
    # Detect PC IP
    # --------------------------------------------------------
    log("Detecting PC IP", "STEP")
    res = pc_executor.execute("hostname -I | awk '{print $1}'")
    pc_ip = (getattr(res, "stdout", "") or "").strip() or pc_name
    log(f"Detected PC IP = {pc_ip}")

    # --------------------------------------------------------
    # Send Invalid Login Attempts
    # --------------------------------------------------------
    log(f"Sending {max_attempts} invalid SSH attempts", "STEP")

    invalid_cmd_template = (
        "sshpass -p '{pw}' ssh "
        "-o StrictHostKeyChecking=no "
        "-o UserKnownHostsFile=/dev/null "
        "-o PubkeyAuthentication=no "
        "-o PasswordAuthentication=yes "
        "-o PreferredAuthentications=password "
        "-o ConnectTimeout=10 {user}@{ip} exit"
    )

    for i in range(1, int(max_attempts) + 1):
        log(f"Invalid Attempt {i}/{max_attempts}")
        cmd = invalid_cmd_template.format(
            pw="wrong_pass",
            user=bb_user,
            ip=bb_ip
        )
        res = pc_executor.execute(cmd)
        log(f"Exit Code = {getattr(res, 'exit_code', 'N/A')}")
        time.sleep(1)

    # --------------------------------------------------------
    # Check Dropbear Logs
    # --------------------------------------------------------
    log("Checking Dropbear logs", "STEP")

    grep_cmd = (
        f"grep \"Bad password attempt for '{bb_user}' from {pc_ip}\" "
        "/var/log/dropbear.log || true"
    )

    dropbear = bb_executor.execute(grep_cmd)
    dropbear_output = (getattr(dropbear, "stdout", "") or "").strip()

    if dropbear_output:
        log("Bad password attempts found in dropbear.log", "PASS")
    else:
        log("No bad-password lines found in dropbear.log", "WARN")

    # --------------------------------------------------------
    # Check Fail2Ban Status
    # --------------------------------------------------------
    log("Checking fail2ban dropbear status", "STEP")

    fb = bb_executor.execute("fail2ban-client status dropbear || true")
    fb_output = getattr(fb, "stdout", "") or ""
    blocked = pc_ip in fb_output

    if blocked:
        log(f"PC IP ({pc_ip}) appears in fail2ban ban list", "PASS")
    else:
        log("PC IP not present in fail2ban ban list", "WARN")

    # --------------------------------------------------------
    # Wait For Unblock
    # --------------------------------------------------------
    max_wait = max(60, int(cooldown_period) * 3)
    deadline = time.time() + max_wait
    poll_interval = 5

    log(f"Polling for unblock (max {max_wait}s)", "STEP")

    valid_cmd_template = (
        "sshpass -p '{pw}' ssh "
        "-o StrictHostKeyChecking=no "
        "-o UserKnownHostsFile=/dev/null "
        "-o PubkeyAuthentication=no "
        "-o PasswordAuthentication=yes "
        "-o PreferredAuthentications=password "
        "-o ConnectTimeout=15 {user}@{ip} echo OK"
    )

    status = "BLOCKED"

    while time.time() < deadline:
        cmd = valid_cmd_template.format(
            pw=bb_pass,
            user=bb_user,
            ip=bb_ip
        )

        resp = pc_executor.execute(cmd)
        output = (getattr(resp, "stdout", "") or "").strip()
        exit_code = getattr(resp, "exit_code", 1)

        if exit_code == 0 and "OK" in output:
            log("LOGIN UNBLOCKED — valid login succeeded", "PASS")
            status = "UNBLOCKED"
            break

        log("Still blocked, retrying...", "WARN")
        time.sleep(poll_interval)

    if status != "UNBLOCKED":
        log("Login still blocked after max wait period", "FAIL")

    total_time = round(time.time() - test_start, 2)

    log(
        f"===== END DoS TEST | STATUS={status} | "
        f"TIME={total_time}s =====",
        "STEP"
    )

    return {
        "status": status,
        "pc_ip": pc_ip,
        "blocked_detected": blocked,
        "total_time_sec": total_time
    }

