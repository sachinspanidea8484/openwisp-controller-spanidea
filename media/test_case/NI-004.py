import os
from datetime import datetime
from robot.api.deco import keyword
from robot.libraries.BuiltIn import BuiltIn
from SSHHelper import SSHConnection

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
# SSH Step: PC -> BB
# =============================
@keyword("SSH PC Then BB")
def ssh_pc_then_bb(pc_ip, pc_user, pc_pass, bb_ip, bb_user, bb_pass):
    """
    Step 1: Login to PC via SSH
    Step 2: From PC, try SSH to BB
    Returns: dict with keys 'exit_code', 'stdout', 'stderr'
    """
    exit_code = 0
    stdout = ""
    stderr = ""

    log_message("🔹 Step 1: Connecting to PC...")

    try:
        # Connect to PC using SSHHelper
        with SSHConnection(pc_ip, pc_user, pc_pass, timeout=10) as ssh_pc:
            log_message(f"✅ Connected to PC ({pc_ip}) successfully")

            # Step 2: Attempt SSH from PC -> BB
            log_message("🔹 Step 2: Attempting SSH from PC to BB...")
            command = f"sshpass -p '{bb_pass}' ssh -o StrictHostKeyChecking=no {bb_user}@{bb_ip} 'echo Connected'"
            res = ssh_pc.execute(command, timeout=10)

            stdout = res.stdout.strip()
            stderr = res.stderr.strip()

            if "Connected" in stdout:
                log_message(f"✅ Successfully logged into BB ({bb_ip}) from PC ({pc_ip})")
                exit_code = 0
            else:
                fail_msg = stderr if stderr else "Unknown error"
                log_message(f"❌ Failed to login to BB ({bb_ip}) from PC ({pc_ip}). Error: {fail_msg}")
                exit_code = 1

    except Exception as e:
        # PC connection failed
        log_message(f"❌ Could not connect to PC ({pc_ip}): {str(e)}")
        exit_code = 1
        stderr = str(e)

    return {'exit_code': exit_code, 'stdout': stdout, 'stderr': stderr}
