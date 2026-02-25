# START_DESCRIPTION
# 1. Initialize custom log file for SSH access control test.
# 2. From the specified PC, attempt SSH login to the BB using valid credentials.
# 3. Use sshpass with StrictHostKeyChecking disabled to avoid host key prompts.
# 4. Execute a simple command (echo ACCESS_OK) on successful login.
# 5. Verify that the command execution is successful and ACCESS_OK is received in output.
# 6. If login fails or ACCESS_OK is not present, mark test as failed.
# 7. Log all stdout, stderr, and execution details in custom log file.
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

def log_message(message):
    timestamped = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    BuiltIn().log_to_console(timestamped)
    with open(LOG_FILE_PATH, "a") as log_file:
        log_file.write(timestamped + "\n")

@keyword("Initialize Custom Log File")
def initialize_custom_log_file():
    log_message("[STEP] Custom log initialized")

@keyword("Log Message To Custom File")
def log_message_to_custom_file(message):
    log_message(message)

@keyword("VERIFY SSH ACCESS PC TO BB")
def verify_ssh_access_pc_to_bb(pc_name, bb_ip, bb_user, bb_pass):

    log_message("========== START ACCESS CONTROL SSH TEST ==========")
    log_message(f"Source PC Device : {pc_name}")
    log_message(f"Destination BB IP: {bb_ip}")

    executor = get_registered_executor(pc_name)

    try:
        log_message("[STEP 1] Attempting login from PC to BB")

        cmd = (
            f"sshpass -p '{bb_pass}' ssh "
            f"-o StrictHostKeyChecking=no "
            f"-o ConnectTimeout=8 "
            f"{bb_user}@{bb_ip} 'echo ACCESS_OK'"
        )

        safe_cmd = cmd.replace(bb_pass, "*****")
        log_message(f"[CMD] {safe_cmd}")

        result = executor.execute(cmd)

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        log_message(f"[STDOUT] {stdout}")
        log_message(f"[STDERR] {stderr}")

        if result.failed:
            raise AssertionError(
                f"command execution failed\nstderr: {stderr}"
            )

        if "ACCESS_OK" not in stdout:
            raise AssertionError(
                f"login did NOT succeed — access likely blocked\nstdout: {stdout}"
            )

        log_message("========== ACCESS VERIFIED SUCCESSFULLY ==========")
        return True

    except AssertionError:
        log_message("========== ACCESS TEST FAILED (ASSERTION) ==========")
        raise

    except Exception as e:
        log_message("========== ACCESS TEST FAILED (EXCEPTION) ==========")
        raise AssertionError(
            f"Unexpected error during access test\n"
            f"{type(e).__name__}: {e}\n"
            f"{traceback.format_exc()}"
        )

