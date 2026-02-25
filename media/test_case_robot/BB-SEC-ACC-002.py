# START_DESCRIPTION
# 1. Initialize custom log file for LuCI web access test.
# 2. From PC, attempt login to BB LuCI interface using HTTP/HTTPS.
# 3. Submit username and password via POST request.
# 4. Verify HTTP 200 response and confirm LuCI dashboard content is returned.
# 5. Store session object for further dashboard verification.
# 6. Access LuCI dashboard page using existing session.
# 7. Confirm dashboard is accessible and content is valid.
# 8. If login or dashboard verification fails, mark test as failed.
# 9. Log HTTP responses and execution details.
# END_DESCRIPTION

import os
import re
import traceback
from datetime import datetime
from robot.api.deco import keyword
from robot.libraries.BuiltIn import BuiltIn
import requests
import urllib3
from execution.executor_helper import get_registered_executor

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =============================
# Logging
# =============================
LOG_FOLDER = os.path.join(os.path.dirname(__file__), '..', '..', 'logs')
os.makedirs(LOG_FOLDER, exist_ok=True)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE_PATH = os.path.join(LOG_FOLDER, f"custom_log_{timestamp}.log")

def log(msg):
    ts = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    BuiltIn().log_to_console(ts)
    try:
        with open(LOG_FILE_PATH, "a") as f:
            f.write(ts + "\n")
    except:
        pass

@keyword("Initialize Custom Log File")
def initialize_custom_log_file():
    log("[STEP] Custom log initialized")

@keyword("Log Message To Custom File")
def log_message_to_custom_file(message):
    log(message)

@keyword("Luci Login From PC")
def luci_login_from_pc(bb_ip, bb_user, bb_pass, test_protocol):
    log(f"[STEP] LuCI login to {bb_ip} using protocol {test_protocol}")
    session = requests.Session()
    login_url = f"{test_protocol}://{bb_ip}/cgi-bin/luci/"
    payload = {
        "luci_username": bb_user,
        "luci_password": bb_pass
    }
    
    try:
        response = session.post(login_url, data=payload, verify=False, timeout=10)
        if response.status_code == 200 and "LuCI" in response.text:
            log("[OK] LuCI login successful")
            BuiltIn().set_suite_variable("${LUCI_SESSION}", session)
            return {"exit_code": 0, "stdout": "LuCI login success", "stderr": ""}
        raise AssertionError(f"LuCI login failed, HTTP {response.status_code}")
    except Exception:
        log("[FAIL] LuCI login failed")
        log(traceback.format_exc())
        return {"exit_code": 1, "stdout": "", "stderr": "LuCI login failed"}

@keyword("Verify LuCI Dashboard From PC")
def verify_luci_dashboard_from_pc(bb_ip, test_protocol):
    log("[STEP] Verifying LuCI dashboard")
    session = BuiltIn().get_variable_value("${LUCI_SESSION}", None)
    if not session:
        BuiltIn().fail("LuCI session not initialized")
    
    try:
        url = f"{test_protocol}://{bb_ip}/cgi-bin/luci/"
        response = session.get(url, verify=False, timeout=10)
        if response.status_code == 200 and "LuCI" in response.text:
            log("[OK] LuCI dashboard verified")
            return {"exit_code": 0, "stdout": "Dashboard OK", "stderr": ""}
        raise AssertionError("LuCI dashboard validation failed")
    except Exception:
        log("[FAIL] LuCI dashboard validation failed")
        log(traceback.format_exc())
        return {"exit_code": 1, "stdout": "", "stderr": "Dashboard validation failed"}

