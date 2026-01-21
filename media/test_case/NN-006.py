import os
import time
from datetime import datetime
from robot.api.deco import keyword
from robot.libraries.BuiltIn import BuiltIn
from SSHHelper import SSHConnection

LOG_FILE_PATH = None


def _rb_log(msg):
    BuiltIn().run_keyword("Log Message To Custom File", msg)


@keyword("Initialize Custom Log File")
def initialize_custom_log_file():
    global LOG_FILE_PATH

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../logs'))
    os.makedirs(log_dir, exist_ok=True)

    LOG_FILE_PATH = os.path.join(log_dir, f"custom_log_{timestamp}.log")
    _rb_log("[STEP] Custom log initialized")


@keyword("Log Message To Custom File")
def log_message_to_custom_file(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_message = f"[{timestamp}] {message}"
    BuiltIn().log_to_console(full_message)

    if LOG_FILE_PATH:
        with open(LOG_FILE_PATH, "a") as f:
            f.write(full_message + "\n")


@keyword("SSH_Perform_Dos_Test")
def ssh_perform_dos_test(
    pc_ip, pc_user, pc_pass,
    bb_ip, bb_user, bb_pass,
    max_attempts, cooldown_period
):
    _rb_log("[STEP] Starting SSH DoS Test")

    try:
        _rb_log(f"[ACTION] Connecting to PC via SSH: {pc_ip}")

        with SSHConnection(pc_ip, pc_user, pc_pass, timeout=10) as ssh_pc:
            _rb_log("✅ Connected to PC")

            # INVALID ATTEMPTS
            for i in range(int(max_attempts)):
                _rb_log(f"[ACTION] Invalid SSH Attempt {i+1}/{max_attempts}")

                cmd_bad = (
                    f"sshpass -p WRONG ssh -o StrictHostKeyChecking=no "
                    f"-o ConnectTimeout=5 {bb_user}@{bb_ip} exit"
                )
                ssh_pc.execute(cmd_bad, timeout=10)
                time.sleep(1)

            _rb_log("[WAIT] Waiting 5 seconds to allow fail2ban block…")
            time.sleep(5)

            # CHECK BLOCKED STATE
            _rb_log("[CHECK] Checking SSH block status…")

            cmd_valid = (
                f"sshpass -p {bb_pass} ssh -o StrictHostKeyChecking=no "
                f"-o ConnectTimeout=5 {bb_user}@{bb_ip} exit"
            )
            res = ssh_pc.execute(cmd_valid, timeout=10)
            stderr = res.stderr.lower()

            if any(x in stderr for x in ["permission denied", "connection refused", "timeout"]):
                _rb_log("🔒 SSH CONNECTION BLOCKED — OK")
            else:
                _rb_log("❌ FAIL — SSH NOT BLOCKED")
                return {"status": "BLOCK_FAILED"}

            # COOLDOWN
            _rb_log(f"[WAIT] Waiting cooldown: {cooldown_period}s")
            time.sleep(int(cooldown_period) + 2)

            # VERIFY UNBLOCK
            _rb_log("[RETRY] Trying valid SSH after cooldown…")
            res = ssh_pc.execute(cmd_valid, timeout=10)
            stderr = res.stderr.lower()

            if "permission denied" not in stderr and "connection refused" not in stderr:
                _rb_log("✅ SSH SUCCESS after cooldown")
                return {"status": "UNBLOCKED"}

            _rb_log("❌ STILL BLOCKED after cooldown")
            return {"status": "STILL_BLOCKED"}

    except Exception as e:
        _rb_log(f"❌ Exception: {str(e)}")
        return {"status": "ERROR", "details": str(e)}
