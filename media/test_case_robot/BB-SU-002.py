# START_DESCRIPTION
# 1. Verify PC login session using 'whoami' command.
# 2. Confirm logged-in username matches expected user.
# 3. From PC, attempt SSH login to DUT (BB) using valid credentials.
# 4. Execute a simple verification command on DUT (e.g., echo BB_CONNECTED).
# 5. Confirm DUT shell/dashboard access is successful.
# 6. If login or command execution fails, mark test as FAILED.
# 7. If access and validation succeed, mark test as PASSED.
# END_DESCRIPTION

import os
from datetime import datetime
from robot.api.deco import keyword
from robot.libraries.BuiltIn import BuiltIn
from execution.executor_helper import get_registered_executor

# ============================================================
# LOGGING SETUP
# ============================================================

LOG_FOLDER = os.path.join(os.path.dirname(__file__), '..', '..', 'logs')
os.makedirs(LOG_FOLDER, exist_ok=True)

LOG_FILE_PATH = os.path.join(
    LOG_FOLDER,
    f"initial_connection_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
)


def log_message(message):
    msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    BuiltIn().log_to_console(msg)
    BuiltIn().log(msg)
    try:
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass


# ============================================================
# COMMON KEYWORDS
# ============================================================

@keyword("Initialize Custom Log File")
def initialize_custom_log_file():
    log_message("===== Initial Connection Log Started =====")


@keyword("Log Message To Custom File")
def log_message_to_custom_file(message):
    log_message(message)


# ============================================================
# VERIFY PC LOGIN
# ============================================================

@keyword("Verify PC Login")
def verify_pc_login(pc_name, expected_user, protocol):
    log_message("[STEP] Verifying PC login credentials")

    executor = get_registered_executor(pc_name)
    command = "whoami"

    log_message(f"[EXEC] {pc_name} -> {command}")
    result = executor.execute(command)

    if result.stdout:
        log_message(f"[STDOUT] {result.stdout.strip()}")
    if result.stderr:
        log_message(f"[STDERR] {result.stderr.strip()}")

    if result.failed:
        raise AssertionError("PC login command failed")

    actual_user = result.stdout.strip()

    # Skip strict validation for MQTT
    if protocol.upper() == "MQTT":
        log_message(
            f"[INFO] MQTT session runs as OS user '{actual_user}', skipping strict user match"
        )
        return True

    if actual_user != expected_user:
        raise AssertionError(
            f"PC login mismatch: expected '{expected_user}', got '{actual_user}'"
        )

    log_message(f"[SUCCESS] PC logged in as expected user: {actual_user}")
    return True


# ============================================================
# VERIFY BB ACCESS FROM PC
# ============================================================

@keyword("Verify DUT Dashboard From PC")
def verify_bb_dashboard_from_pc(pc_name, bb_ip, bb_user, bb_pass):
    log_message("[STEP] Verifying BB access from PC")

    executor = get_registered_executor(pc_name)

    command = (
        f"sshpass -p '{bb_pass}' ssh "
        f"-o StrictHostKeyChecking=no "
        f"-o ConnectTimeout=5 "
        f"{bb_user}@{bb_ip} 'echo BB_CONNECTED'"
    )

    log_message(f"[EXEC] {pc_name} -> {command}")
    result = executor.execute(command)

    if result.stdout:
        log_message(f"[STDOUT] {result.stdout.strip()}")
    if result.stderr:
        log_message(f"[STDERR] {result.stderr.strip()}")

    if result.failed or "BB_CONNECTED" not in result.stdout:
        raise AssertionError("DUT dashboard/shell access failed from PC")

    log_message("[SUCCESS] DUT dashboard reachable from PC")
    return True

