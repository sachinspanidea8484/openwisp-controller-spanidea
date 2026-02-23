#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unified MQTT Agent for OpenWrt Device
Handles both:
1. Test execution (NB Agent functionality)
2. Command execution (Robot Agent functionality)
"""


import subprocess
import json
import cgi
import fcntl
import sys
import os
import time
import signal
import threading
from datetime import datetime, timezone
import select
import paho.mqtt.client as mqtt
import logging
from queue import Queue
import shlex

IS_OVERRIDE_TEST_CASE=True 
# ===== CONFIGURATION =====
CONFIG = {
    "SCRIPTS_DIR": "/usr/bin/tests",
    "DOWNLOAD_URL": "http://10.10.10.10:8000/media/test_case/",
    "RESULT_API": "http://10.10.10.10:8000/api/v1/test-management/device-test-result/",
    "LOCK_FILE": "/tmp/test_runner.lock",
    "LOG_FILE": "/var/log/mqtt_agent.log",
    "TIMEOUT": 86400,  # 24 hours max timeout
    "CURRENT_TEST_FILE": "/tmp/current_test.json",
    
    # Stuck detection settings
    "PROGRESS_TIMEOUT": 600,      # 10 minutes - if no output, consider stuck
    "STUCK_CHECK_INTERVAL": 120,   # Check every 30 seconds for stuck process
    "FORCE_KILL_TIMEOUT": 60,     # Time to wait before force killing
    "DEBUG_MODE": True,           # Enable detailed logging
    "MAX_WAIT_FOR_LOCK": 300,     # Max time to wait for lock (5 minutes)
    "MQTT_BROKER_IP": "10.10.10.10",        # MQTT broker IP
    "MQTT_BROKER_PORT": 1883,       # MQTT broker port
    "DEVICE_ID": "3effd7c4-3890-42fd-bc02-b7c370a647c4",  #Device UUID from openwisp
    "KEEPALIVE": 60,
    "RECONNECT_DELAY": 10
}

# Global variable to track monitoring thread
_monitor_thread = None
_current_test_info = {}

# ===== HELPER FUNCTIONS =====
def log_message(message, level="INFO"):
    """Enhanced logging with levels"""
    try:
        if CONFIG["DEBUG_MODE"]:
            logging.info(message)
    except:
        pass

# NB Topics
TOPIC_CMD = f"tests/device/{CONFIG['DEVICE_ID']}/run"
TOPIC_RES = f"tests/device/{CONFIG['DEVICE_ID']}/result"

# Robot Topics
COMMAND_TOPIC = f"device/{CONFIG['DEVICE_ID']}/command"
RESPONSE_TOPIC = f"device/{CONFIG['DEVICE_ID']}/response"




# Keep track of running process
current_process = None
current_test_id = None
current_execution_id = None
current_test_suite_execution_id = None  # ADD THIS LINE
test_queue = Queue()
queue_lock = threading.Lock()
proc_lock = threading.Lock()
aborted = False
mqtt_client = None
    
# When connected to broker
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        log_message("[Agent] Connected to broker")
        # Subscribe to both NB and Robot topics
        client.subscribe(TOPIC_CMD)
        client.subscribe(COMMAND_TOPIC)
        log_message(f"[Agent] Subscribed to {TOPIC_CMD}")
        log_message(f"[Agent] Subscribed to {COMMAND_TOPIC}")
    else:
        log_message(f"[Agent] Failed to connect, code {rc}")

def on_disconnect(client, userdata, rc):
    log_message(f"[Agent] Disconnected (rc={rc}). Will retry...")

# When mqtt message received
def on_message(client, userdata, msg):
    """
    Unified message handler for both NB and Robot commands
    Routes to appropriate handler based on topic
    """
    global current_test_suite_execution_id  # ADD THIS LINE
    payload = msg.payload.decode()
    log_message(f"Received message: {payload}")
    

    try:
        topic = msg.topic
        payload = msg.payload.decode() 
        data = json.loads(payload)


        if topic == COMMAND_TOPIC:
          return  handle_robot_message(client, payload)
        
        command_type = data.get("command_type", "").lower()
        execution_id = data.get("execution_id")
        test_json_str = data.get("test_json_str")
        log_message(f"test_json_str>>>>>: {test_json_str}")





        test_id = data.get("test_id")
        test_suite_execution_id = data.get("test_suite_execution_id")  # ADD THIS LINE

        if command_type == "abort":
            abort_test(test_id, execution_id)
        elif command_type == "run":
            with queue_lock:
                current_test_suite_execution_id = test_suite_execution_id
                is_file_required = data.get("is_file_required", False)
                file_download_url = data.get("file_download_url")
                
                # Store file parameters as function attributes for execute_test to access
                execute_test.is_file_required = is_file_required
                execute_test.file_download_url = file_download_url
                
                log_message(f"Queueing test {test_id} for execution")
                log_message(f"File required: {is_file_required}, URL: {file_download_url}")
                test_queue.put((test_id, execution_id, test_json_str))
            log_message(f"Unknown command_type: {command_type}")

    except Exception as e:
        log_message(f"Error processing message: {e}")


# Worker thread to execute test cases
def worker_thread():
    """Thread that processes queued tests sequentially."""
    global current_process, current_test_id, current_execution_id, aborted
    while True:
        test_info = test_queue.get()
        if test_info is None:
            break

        test_id, execution_id ,test_json_str = test_info
        current_test_id = test_id
        current_execution_id = execution_id
        log_message(f"Executing test: {test_id}, with Execution id: {execution_id}")
        execute_test(test_id, execution_id ,test_json_str)

# ---------------------------------------------------
def abort_test(abort_test_id, abort_execution_id):
    """Abort test if running or queued."""
    global current_process, current_test_id, current_execution_id, aborted
    aborted = False
    log_message(f"Current test: {current_test_id}, and current Execution id: {current_execution_id}")
    log_message(f"Aborting test: {abort_test_id}, and aborting Execution id: {abort_execution_id}")

    # Abort if currently running
    with proc_lock:
        log_message("Got proc lock")
        if current_process and current_process.poll() is None and current_test_id == abort_test_id and current_execution_id == abort_execution_id:
            log_message(f"Aborting currently running test: {abort_test_id}, with execution id: {abort_execution_id}")
            try:
                current_process.terminate()
                current_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                current_process.kill()
            
            aborted = True

    # Remove from queue if waiting
    with queue_lock:
        new_queue = Queue()
        removed = False
        while not test_queue.empty():
            test_id, exec_id ,test_json_str = test_queue.get()
            if test_id != abort_test_id or exec_id != abort_execution_id:
                new_queue.put((test_id, exec_id ,test_json_str))
            else:
                removed = True
                log_message(f"Removed queued test: {abort_test_id} with Execution ID: {abort_execution_id}")
        while not new_queue.empty():
            test_queue.put(new_queue.get())

    if not aborted and not removed:
        log_message(f"No active or queued test found with ID: {abort_test_id} and Execution ID: {abort_execution_id}")

def send_response(test_id, execution_id, status, message="", stdout="", stderr="", exit_code=0, duration=0):
    """Send JSON response to client"""
    print("Content-Type: application/json")
    print()

    response = {
        "test_id": test_id,
        "execution_id": execution_id,
        "status": status,
        "message": message,
        "exit_code": exit_code,
        "duration": duration,
        "timestamp": get_iso_timestamp()
    }

    if stdout:
        response["stdout"] = stdout
    if stderr:
        response["stderr"] = stderr

    print(json.dumps(response, indent=2))
    sys.stdout.flush()

def get_iso_timestamp():
    """Get current time in ISO format"""
    return datetime.now(timezone.utc).isoformat()

def update_test_status_api(execution_id, status, exit_code=0, stdout="", stderr="", started_at=None, completed_at=None, device_rebooting=False):
    """
    Send test status updates back to executor server via MQTT
    """
    global mqtt_client, current_test_id, current_test_suite_execution_id  # MODIFY THIS LINE
    
    log_message("="*40)
    log_message("SENDING STATUS UPDATE VIA MQTT")
    log_message(f"Execution ID: {execution_id}")
    log_message(f"Test ID: {current_test_id}")
    log_message(f"Test Suite ID: {current_test_suite_execution_id}")  # ADD THIS LINE
    log_message(f"Device ID: {CONFIG['DEVICE_ID']}")  # ADD THIS LINE
    log_message(f"Status: {status}")
    log_message(f"Exit code: {exit_code}")

    # Map status correctly for final results
    if status not in ["running", "timeout", "cancelled", "aborted"]:
        if exit_code != 0:
            status = "failed"
            log_message(f"Status mapped to 'failed' due to exit_code {exit_code}")
        elif exit_code == 0:
            status = "success"
            log_message(f"Status mapped to 'success' due to exit_code 0")


    # FIX: Build result dict conditionally
    result_data = {
    "exit_code": exit_code,
    "stdout": stdout[:50000] if stdout else "",
    "stderr": stderr[:50000] if stderr else "",
    "started_at": started_at ,
    
         }        
    result_data["completed_at"] = completed_at

    # BUILD MQTT PAYLOAD
    payload = {
        "execution_id": execution_id,
        "test_id": current_test_id,
        "status": status,
        "device_id": CONFIG["DEVICE_ID"],  # ADD THIS LINE
        "test_suite_execution_id": current_test_suite_execution_id or execution_id,  # ADD THIS LINE
        "result": result_data,  # Use conditional dict
        "timestamp": get_iso_timestamp(),
        "device_rebooting": device_rebooting
    }

    log_message(f"Payload size: {len(json.dumps(payload))} bytes")
    log_message(f"Publishing to topic: {TOPIC_RES}")
    
    # CHECK MQTT CLIENT
    if mqtt_client is None or not mqtt_client.is_connected():
        log_message("[ERROR] MQTT client not connected! Cannot send result.", "ERROR")
        
        # Fallback: Try HTTP API as backup (only for final results)
        if status != "running":
            log_message("Attempting fallback via HTTP API...")
            return send_result_with_wget(execution_id, payload)
        return False
    
    # PUBLISH STATUS UPDATE TO EXECUTOR
    try:
        result = mqtt_client.publish(
            topic=TOPIC_RES,
            payload=json.dumps(payload),
            qos=1,
            retain=False
        )
        
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            log_message(f"[SUCCESS] Status '{status}' published successfully via MQTT (MID: {result.mid})", "INFO")
            return True
        else:
            log_message(f"[ERROR] MQTT publish failed with code: {result.rc}", "ERROR")
            # Fallback to HTTP (only for final results)
            if status != "running":
                return send_result_with_wget(execution_id, payload)
            return False
            
    except Exception as e:
        log_message(f"[ERROR] MQTT publish exception: {str(e)}", "ERROR")
        # Fallback to HTTP (only for final results)
        if status != "running":
            return send_result_with_wget(execution_id, payload)
        return False

def send_result_with_wget(execution_id, mqtt_payload):
    """
    Alternative method using wget to send results
    Converts MQTT payload format to API format
    """
    log_message("Trying alternative method with wget...")

    # Convert MQTT payload to API format
    api_payload = {
        "execution_id": mqtt_payload["execution_id"],
        "test_id": mqtt_payload.get("test_id"),  # ADD THIS LINE
        "device_id": mqtt_payload.get("device_id"),  # ADD THIS LINE
        "test_suite_execution_id": mqtt_payload.get("test_suite_execution_id"),  # ADD THIS LINE
        "status": mqtt_payload["status"],
        "exit_code": mqtt_payload["result"]["exit_code"],
        "stdout": mqtt_payload["result"]["stdout"],
        "stderr": mqtt_payload["result"]["stderr"],
        "started_at": mqtt_payload["result"]["started_at"],
        "completed_at": mqtt_payload["result"]["completed_at"]
    }

    temp_file = f"/tmp/payload_{execution_id}.json"
    try:
        with open(temp_file, "w") as f:
            json.dump(api_payload, f)
        
        wget_cmd = [
            "wget",
            "-O", "-",
            "--post-file", temp_file,
            "--header", "Content-Type: application/json",
            "--timeout", "30",
            "-q",
            CONFIG["RESULT_API"]
        ]
        
        result = subprocess.run(wget_cmd, capture_output=True, text=True)
        log_message(f"Wget return code: {result.returncode}")
        
        if result.returncode == 0:
            log_message("[SUCCESS] Successfully sent result via wget")
            return True
        else:
            log_message(f"[ERROR] Wget failed: {result.stderr}")
            return False
            
    except Exception as e:
        log_message(f"[ERROR] Error with wget: {str(e)}")
        return False
    finally:
        try:
            os.remove(temp_file)
        except:
            pass

def set_current_test_info(test_id, execution_id, process_pid=None):
    """Save current test information with enhanced tracking"""
    global _current_test_info
    
    info = {
        "test_id": test_id,
        "execution_id": execution_id,
        "started_at": get_iso_timestamp(),
        "last_activity": get_iso_timestamp(),
        "main_pid": os.getpid(),
        "test_process_pid": process_pid,
        "status": "running"
    }
    
    _current_test_info = info
    
    try:
        with open(CONFIG["CURRENT_TEST_FILE"], "w") as f:
            json.dump(info, f, indent=2)
        log_message(f"Updated current test info: PID {process_pid}, Main PID {os.getpid()}")
    except Exception as e:
        log_message(f"Error saving test info: {e}", "WARNING")

def update_test_activity():
    """Update last activity timestamp"""
    global _current_test_info
    
    current_time = get_iso_timestamp()
    _current_test_info["last_activity"] = current_time
    
    try:
        if os.path.exists(CONFIG["CURRENT_TEST_FILE"]):
            with open(CONFIG["CURRENT_TEST_FILE"], "r") as f:
                info = json.load(f)
            
            info["last_activity"] = current_time
            
            with open(CONFIG["CURRENT_TEST_FILE"], "w") as f:
                json.dump(info, f, indent=2)
    except Exception as e:
        log_message(f"Error updating activity: {e}", "WARNING")

def clear_current_test_info():
    """Clear current test information"""
    global _current_test_info, current_process, current_test_id, current_execution_id
    _current_test_info = {}
    current_process = None
    current_test_id = None
    current_execution_id = None
    
    try:
        if os.path.exists(CONFIG["CURRENT_TEST_FILE"]):
            os.remove(CONFIG["CURRENT_TEST_FILE"])
    except:
        pass

def is_process_alive(pid):
    """Check if a process is still alive"""
    if not pid:
        return False
    
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def kill_stuck_process(test_info):
    """Kill a stuck test process"""
    test_pid = test_info.get("test_process_pid")
    execution_id = test_info.get("execution_id")
    test_id = test_info.get("test_id")
    
    if not test_pid:
        log_message("No test process PID found to kill", "WARNING")
        return False
    
    log_message(f"KILLING STUCK TEST PROCESS: {test_id} (PID: {test_pid})", "WARNING")
    
    try:
        if is_process_alive(test_pid):
            # First try graceful termination
            os.kill(test_pid, signal.SIGTERM)
            log_message(f"Sent SIGTERM to test process PID {test_pid}")
            
            # Wait for graceful shutdown
            time.sleep(CONFIG["FORCE_KILL_TIMEOUT"])
            
            # Check if still alive
            if is_process_alive(test_pid):
                # Force kill
                os.kill(test_pid, signal.SIGKILL)
                log_message(f"Force killed test process PID {test_pid} with SIGKILL", "WARNING")
            else:
                log_message(f"Test process {test_pid} terminated gracefully")
        
        # Update API with timeout status
        update_test_status_api(
            execution_id,
            "timeout",
            exit_code=124,
            stderr=f"Test killed due to inactivity timeout (>{CONFIG['PROGRESS_TIMEOUT']}s)",
            started_at=test_info.get("started_at"),
            completed_at=get_iso_timestamp()
        )
        
        return True
        
    except ProcessLookupError:
        log_message(f"Test process {test_pid} already dead")
        return True
    except Exception as e:
        log_message(f"Error killing stuck process: {e}", "ERROR")
        return False

def monitor_stuck_tests():
    """Monitor current test for stuck condition"""
    global _current_test_info
    
    log_message("Started stuck test monitor thread", "INFO")
    
    while True:
        try:
            time.sleep(CONFIG["STUCK_CHECK_INTERVAL"])
            
            # Check if there's a current test running
            if not _current_test_info:
                continue
                
            current_time = datetime.now(timezone.utc)
            last_activity_str = _current_test_info.get("last_activity")
            
            if not last_activity_str:
                continue
            
            # Calculate inactive time
            try:
                last_activity = datetime.fromisoformat(last_activity_str.replace('Z', '+00:00'))
                inactive_time = (current_time - last_activity).total_seconds()
                
                log_message(f"Current test inactive for {int(inactive_time)} seconds", "DEBUG")
                
                # Check if test is stuck
                if inactive_time > CONFIG["PROGRESS_TIMEOUT"]:
                    log_message(f"TEST IS STUCK! No output for {int(inactive_time)} seconds", "ERROR")
                    
                    # Kill the stuck process
                    if kill_stuck_process(_current_test_info):
                        log_message("Successfully killed stuck test process", "INFO")
                    else:
                        log_message("Failed to kill stuck test process", "ERROR")
                    
                    # Clear current test info
                    clear_current_test_info()
                
            except Exception as e:
                log_message(f"Error parsing last activity time: {e}", "WARNING")
                
        except Exception as e:
            log_message(f"Error in stuck test monitor: {e}", "ERROR")
            time.sleep(30)  # Wait before retrying

def start_stuck_monitor():
    """Start the stuck test monitoring thread"""
    global _monitor_thread
    
    if _monitor_thread is None or not _monitor_thread.is_alive():
        _monitor_thread = threading.Thread(target=monitor_stuck_tests, daemon=True)
        _monitor_thread.start()
        log_message("Started stuck test monitoring thread", "INFO")


def download_test_script(test_id, helpers=None):
    """Download test script and helper files from server
    
    Args:
        test_id: The ID of the test script to download
        helpers: List of helper file names to download
        IS_OVERRIDE_TEST_CASE: Boolean flag to control whether to download/override existing file
    """
    # Set default helpers if None
    if helpers is None:
        helpers = ["common_helper.py"]
    
    script_name = f"{test_id}.py"
    script_path = os.path.join(CONFIG["SCRIPTS_DIR"], script_name)
    script_url = CONFIG["DOWNLOAD_URL"] + script_name

    log_message(f"DOWNLOAD PHASE STARTED")
    log_message(f"Script name: {script_name}")
    log_message(f"Override mode: {IS_OVERRIDE_TEST_CASE}")
    
    # If override is False and file already exists, use existing file
    if not IS_OVERRIDE_TEST_CASE and os.path.exists(script_path):
        log_message(f"Using existing file: {script_path}")
        file_size = os.path.getsize(script_path)
        log_message(f"Existing file size: {file_size} bytes")
        
        # Log first few lines of existing file
        try:
            with open(script_path, 'r') as f:
                lines = f.readlines()[:5]
                log_message("First 5 lines of existing script:")
                for i, line in enumerate(lines, 1):
                    log_message(f"  Line {i}: {line.rstrip()}")
        except:
            pass
            
        # Still download helper files even if test case exists
        download_helper_files(helpers)
        return True, script_path
    
    # If override is True or file doesn't exist, download it
    log_message(f"Download URL: {script_url}")
    log_message(f"Save path: {script_path}")
    
    os.makedirs(CONFIG["SCRIPTS_DIR"], exist_ok=True)
    
    # Download and save to file
    cmd = ["wget", "-O", script_path, "--timeout=30", "-q", script_url]
    log_message(f"Executing command: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        log_message(f"DOWNLOAD FAILED!")
        log_message(f"Return code: {result.returncode}")
        log_message(f"Error: {result.stderr}")
        return False, result.stderr

    # Log file details after download
    if os.path.exists(script_path):
        file_size = os.path.getsize(script_path)
        log_message(f"DOWNLOAD SUCCESS!")
        log_message(f"File size: {file_size} bytes")
        os.chmod(script_path, 0o755)
        
        # Log first few lines for verification
        try:
            with open(script_path, 'r') as f:
                lines = f.readlines()[:5]
                log_message("First 5 lines of downloaded script:")
                for i, line in enumerate(lines, 1):
                    log_message(f"  Line {i}: {line.rstrip()}")
        except:
            pass
    
    # Download helper files
    download_helper_files(helpers)

    return True, script_path

def download_helper_files(helpers):
    """Download helper files to the scripts directory
    
    Args:
        helpers: List of helper file names (e.g., ["common_helper.py"])
    """
    if not helpers or not isinstance(helpers, list):
        log_message("No helper files to download")
        return
    
    log_message(f"\nDownloading helper files...")
    os.makedirs(CONFIG["SCRIPTS_DIR"], exist_ok=True)
    
    for helper_name in helpers:
        helper_url = CONFIG["DOWNLOAD_URL"] + helper_name
        helper_path = os.path.join(CONFIG["SCRIPTS_DIR"], helper_name)
        
        log_message(f"Helper URL: {helper_url}")
        log_message(f"Helper path: {helper_path}")
        
        try:
            # Download helper file
            cmd = ["wget", "-O", helper_path, "--timeout=30", "-q", helper_url]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                log_message(f"Warning: Failed to download {helper_name}: {result.stderr}")
                continue
            
            # Make executable
            if os.path.exists(helper_path):
                os.chmod(helper_path, 0o755)
                file_size = os.path.getsize(helper_path)
                log_message(f"Downloaded {helper_name} ({file_size} bytes)")
            else:
                log_message(f"Warning: {helper_name} not found after download")
                
        except Exception as e:
            log_message(f"Warning: Error downloading {helper_name}: {str(e)}")

def execute_test_with_monitoring(script_path, execution_id, timeout ,test_json_str):
    """Execute test with real-time output logging and stuck detection"""
    global current_process
    log_message(f"Starting monitored execution: {script_path}")
    log_message(f"test_json_str: {test_json_str}")

    
    stdout_lines = []
    stderr_lines = []
    start_time = time.time()

    

    try:
        # Start the process
        cmd = ["python3", "-u", script_path, f"CONFIGURATION={test_json_str}"]
        log_message(f"cmd>>>>>>>>>>>>: {cmd}")
   


        process = subprocess.Popen(
         cmd,
         stdout=subprocess.PIPE,
         stderr=subprocess.PIPE,
         text=True,
         bufsize=1,  # Line buffered
         cwd=CONFIG["SCRIPTS_DIR"],
         env={**os.environ, "PYTHONUNBUFFERED": "1"}
       )
        current_process = process
        
        log_message(f"Test process started with PID: {process.pid}")
        
        # Update current test info with process PID
        test_id = os.path.basename(script_path).replace('.py', '')
        set_current_test_info(test_id, execution_id, process.pid)
        
        # Set up non-blocking I/O
        flags = fcntl.fcntl(process.stdout, fcntl.F_GETFL)
        fcntl.fcntl(process.stdout, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        flags = fcntl.fcntl(process.stderr, fcntl.F_GETFL)
        fcntl.fcntl(process.stderr, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        
        # Monitor output in real-time
        while True:
            # Check if process is still running
            poll_status = process.poll()
            
            # Check for timeout
            if time.time() - start_time > timeout:
                log_message(f"TEST TIMEOUT after {timeout} seconds!", "ERROR")
                process.terminate()
                time.sleep(2)
                if process.poll() is None:
                    process.kill()
                
                return {
                    "exit_code": 124,
                    "stdout": '\n'.join(stdout_lines),
                    "stderr": '\n'.join(stderr_lines) + f"\nTest execution timeout ({timeout}s)",
                    "timeout": True,
                    "device_rebooting": False
                }
            
            # Read available stdout
            output_received = False
            reboot_requested = False
            make_test_passed_on_timeout = False
            try:
                while True:
                    line = process.stdout.readline()
                    if not line:
                        break
                    line = line.rstrip()
                    if line:
                        if "REBOOT_TRIGGER" in line:
                            reboot_requested = True
                            break
                        elif "MARK_TEST_PASSED_ON_TIMEOUT" in line:
                            make_test_passed_on_timeout = True
                            break
                        stdout_lines.append(line)
                        log_message(f"[STDOUT] {line}", "DEBUG")
                        output_received = True
                if reboot_requested:
                    return {                                                        
                        "exit_code": 0,                                           
                        "stdout": '\n'.join(stdout_lines),                          
                        "stderr": '\n'.join(stderr_lines),
                        "timeout": False,
                        "device_rebooting": True                                             
                    }
                elif make_test_passed_on_timeout:
                    return {                                                        
                        "exit_code": 0,                                           
                        "stdout": '\n'.join(stdout_lines),                          
                        "stderr": '\n'.join(stderr_lines),
                        "timeout": False,
                        "make_test_passed_on_timeout": True                                             
                    }
            except IOError:
                pass
            
            # Read available stderr
            try:
                while True:
                    line = process.stderr.readline()
                    if not line:
                        break
                    line = line.rstrip()
                    if line:
                        stderr_lines.append(line)
                        log_message(f"[STDERR] {line}", "WARNING")
                        output_received = True
            except IOError:
                pass
            
            # Update activity if we received output
            if output_received:
                update_test_activity()
            
            # If process has finished, do one final read and exit
            if poll_status is not None:
                # Final read to ensure we get all output
                time.sleep(0.1)
                
                # Final stdout read
                try:
                    remaining = process.stdout.read()
                    if remaining:
                        for line in remaining.strip().split('\n'):
                            if line:
                                stdout_lines.append(line)
                                log_message(f"[STDOUT-FINAL] {line}", "DEBUG")
                except:
                    pass
                
                # Final stderr read
                try:
                    remaining = process.stderr.read()
                    if remaining:
                        for line in remaining.strip().split('\n'):
                            if line:
                                stderr_lines.append(line)
                                log_message(f"[STDERR-FINAL] {line}", "WARNING")
                except:
                    pass
                
                log_message(f"Test completed with exit code: {poll_status}")
                
                return {
                    "exit_code": poll_status,
                    "stdout": '\n'.join(stdout_lines),
                    "stderr": '\n'.join(stderr_lines),
                    "timeout": False,
                    "device_rebooting": False
                }
            
            # Small sleep to prevent CPU spinning
            time.sleep(0.1)
            
    except Exception as e:
        log_message(f"EXCEPTION during test execution: {str(e)}", "ERROR")
        
        # Try to kill the process if it's still running
        try:
            if 'process' in locals():
                process.terminate()
                time.sleep(2)
                if process.poll() is None:
                    process.kill()
        except:
            pass
        
        return {
            "exit_code": -1,
            "stdout": '\n'.join(stdout_lines),
            "stderr": '\n'.join(stderr_lines) + f"\nExecution error: {str(e)}",
            "timeout": False,
            "device_rebooting": False
        }

def execute_test(test_id, execution_id ,test_json_str):
    """Execute test and return results with stuck detection"""
    start_time = time.time()
    started_at = get_iso_timestamp()
    lock_file = None

    try:
        # Try to acquire exclusive lock with timeout
        lock_file = open(CONFIG["LOCK_FILE"], "w")
        
        log_message(f"Attempting to acquire lock for test {test_id}")
        
        # Try non-blocking lock first
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            log_message(f"Lock acquired immediately for test {test_id}")
        except IOError:
            # Another test is running, inform user and wait with timeout
            log_message(f"Another test is running, checking status...")
            
            # Check current test status
            current_test = {}
            if os.path.exists(CONFIG["CURRENT_TEST_FILE"]):
                try:
                    with open(CONFIG["CURRENT_TEST_FILE"], "r") as f:
                        current_test = json.load(f)
                except:
                    pass
            
            running_test_id = current_test.get("test_id", "Unknown")
            running_since = current_test.get("started_at", "Unknown")
            
            log_message(f"Waiting for lock (max {CONFIG['MAX_WAIT_FOR_LOCK']}s)...")
            
            # Set timeout for lock acquisition
            signal.signal(signal.SIGALRM, lambda s, f: None)
            signal.alarm(CONFIG['MAX_WAIT_FOR_LOCK'])
            
            try:
                fcntl.flock(lock_file, fcntl.LOCK_EX)
                signal.alarm(0)  # Cancel timeout
                log_message(f"Lock acquired after waiting for test {test_id}")
            except:
                signal.alarm(0)  # Cancel timeout
                log_message(f"Timeout waiting for lock", "ERROR")
                return
        
        # Start the stuck monitor if not already running
        start_stuck_monitor()
        
        # Set current test info
        set_current_test_info(test_id, execution_id)
        
        log_message(f"Starting test {test_id} (execution: {execution_id})")

        # ===== HANDLE CONFIGURATION FILE DOWNLOAD (if required) =====
        # Extract is_file_required and file_download_url from the message payload
        # These should be stored when on_message receives them
        is_file_required = getattr(execute_test, 'is_file_required', False)
        file_download_url = getattr(execute_test, 'file_download_url', None)

        if is_file_required and file_download_url:
            log_message(f"\n Step 5.5: Handling configuration file...")
            success, result = download_and_prepare_config_file(file_download_url, execution_id)
            
            if not success:
                duration = int(time.time() - start_time)
                completed_at = get_iso_timestamp()
                
                # Send final "failed" result
                update_test_status_api(
                    execution_id,
                    "failed",
                    exit_code=-1,
                    stderr=f"Configuration file download failed: {result}",
                    started_at=started_at,
                    completed_at=completed_at
                )
                
                test_queue.task_done()
                return
            
            log_message(f"Configuration file ready at: {result}")
        else:
            log_message(f"\nStep 5.5: No configuration file required")

        
        # SEND "RUNNING" STATUS TO EXECUTOR VIA MQTT
        log_message("[SENDING] Sending 'running' status to executor...")
        api_result = update_test_status_api(
            execution_id, 
            "running", 
            started_at=started_at,
            exit_code=0,
            stdout="",
            stderr=""
        )
        if not api_result:
            log_message("[WARNING] Failed to send 'running' status to executor", "WARNING")
        else:
            log_message("[SUCCESS] 'Running' status sent to executor successfully")
        
        # Download test script
        success, result = download_test_script(test_id)
        if not success:
            duration = int(time.time() - start_time)
            completed_at = get_iso_timestamp()
            
            # Send final "failed" result
            update_test_status_api(
                execution_id,
                "failed",
                exit_code=-1,
                stderr=f"Test case '{test_id}' does not exist for the given ID.",
                started_at=started_at,
                completed_at=completed_at
            )
            
            test_queue.task_done()
            return
        
        script_path = result
        
        # Execute the test with monitoring
        
        log_message(f"Executing test script {test_id}.py")
        result = execute_test_with_monitoring(script_path, execution_id, CONFIG["TIMEOUT"] ,test_json_str)
        
        stdlogs = result["stdout"]
        # Determine status
        if result["timeout"]:
            status = "timeout"
        elif result["exit_code"] == 0:
            status = "success"
        elif result["exit_code"] == -15:
            status = "aborted"
            result["stdout"] += "\nTest aborted by user\n"
            result["stderr"] += "\nTest aborted by user\n"
        else:
            status = "failed"
        
        duration = int(time.time() - start_time)
        completed_at = get_iso_timestamp()
        
        log_message(f"Test completed with status: {status}, exit code: {result['exit_code']}")
        
        # Send final result with completed_at
        log_message("[SENDING] Sending final result to executor...")
        api_success = update_test_status_api(
            execution_id,
            status,
            exit_code=result["exit_code"],
            stdout=result["stdout"],
            stderr=result["stderr"],
            started_at=started_at,
            completed_at=completed_at,
            device_rebooting=result["device_rebooting"]
        )
        
        if not api_success:
            log_message("[ERROR] Failed to save final result to executor!", "ERROR")
            # Save result locally as backup
            backup_file = f"/tmp/test_result_{execution_id}.json"
            try:
                with open(backup_file, "w") as f:
                    json.dump({
                        "execution_id": execution_id,
                        "test_id": test_id,
                        "status": status,
                        "exit_code": result["exit_code"],
                        "stdout": result["stdout"],
                        "stderr": result["stderr"],
                        "started_at": started_at,
                        "completed_at": completed_at
                    }, f, indent=2)
                log_message(f"[SAVED] Saved result locally to {backup_file}")
            except:
                pass
        else:
            log_message("[SUCCESS] Final result sent to executor successfully")
        
    except Exception as e:
        log_message(f"[ERROR] Error in test execution: {str(e)}", "ERROR")
        duration = int(time.time() - start_time)
        completed_at = get_iso_timestamp()
        
        # Update executor with error
        update_test_status_api(
            execution_id,
            "failed",
            exit_code=-1,
            stderr=str(e),
            started_at=started_at,
            completed_at=completed_at
        )
        
    finally:
        # Clear current test info
        clear_current_test_info()
        test_queue.task_done()
        
        # Release lock
        if lock_file:
            try:
                fcntl.flock(lock_file, fcntl.LOCK_UN)
                lock_file.close()
            except:
                pass
        
        log_message(f"Test {test_id} (execution: {execution_id}) finished")
        log_message("="*60)



# ===== ROBOT MESSAGE HANDLER (New addition) =====
def handle_robot_message(client, payload):
    """
    Handle Robot Framework command execution
    Executes commands immediately (no queuing)
    """
    log_message("")
    log_message("="*70)
    log_message("[ROBOT] New command received")
    
    try:
        data = json.loads(payload)
        command = data.get("command", "")
        execution_id = data.get("execution_id", "unknown")
        
        if not command:
            log_message("[ROBOT] No command in payload")
            return
        
        log_message(f"[ROBOT] Command: {command}")
        log_message(f"[ROBOT] Execution ID: {execution_id}")
        
        # Execute command immediately (blocking)
        result = execute_robot_command(command)
        
        # Add execution_id to response
        result["execution_id"] = execution_id
        
        # Send response back
        response_json = json.dumps(result)
        client.publish(RESPONSE_TOPIC, response_json, qos=1)
        
        log_message(f"[ROBOT] Response sent to: {RESPONSE_TOPIC}")
        log_message(f"[ROBOT] Execution ID: {execution_id}")
        log_message("="*70)
        log_message("")
        
    except json.JSONDecodeError as e:
        log_message(f"[ROBOT] Invalid JSON: {str(e)}")
    except Exception as e:
        log_message(f"[ROBOT] Error processing message: {str(e)}")



# ===== ROBOT COMMAND EXECUTION =====
def execute_robot_command(command):
    """
    Execute shell command for Robot Framework
    BLOCKING - waits for command to complete
    """
    log_message(f"[ROBOT] Executing: {command}")
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
            text=True
        )
        
        response = {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
            "timestamp": datetime.now().isoformat()
        }
        
        log_message(f"[ROBOT] Command completed (exit_code: {result.returncode})")
        
        if result.stdout:
            log_message(f"[ROBOT] Output: {result.stdout[:100]}...")
        if result.stderr:
            log_message(f"[ROBOT] Error: {result.stderr[:100]}...")
        
        return response
        
    except subprocess.TimeoutExpired:
        log_message("[ROBOT] Command timeout (60s)")
        return {
            "stdout": "",
            "stderr": "Command timeout after 60 seconds",
            "exit_code": -1,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        log_message(f"[ROBOT] Execution error: {str(e)}")
        return {
            "stdout": "",
            "stderr": str(e),
            "exit_code": -1,
            "timestamp": datetime.now().isoformat()
        }


def download_and_prepare_config_file(file_download_url, execution_id):
    """
    Download and prepare configuration file (similar to SSH implementation)
    Handles: .tar.gz, .tar.bz2, .gz, .bz2, .tar, and other files
    Returns: (success, remote_path_or_error)
    """
    import gzip
    import bz2
    import shutil
    import tarfile
    
    log_message(f"Downloading configuration file...")
    log_message(f"Download URL: {file_download_url}")
    
    local_config_file = None
    
    try:
        # Get filename and extension
        original_filename = file_download_url.split('/')[-1].split('?')[0]
        
        # Handle compound extensions (.tar.gz, .tar.bz2, etc.)
        if '.tar.' in original_filename:
            file_ext = original_filename[original_filename.index('.tar'):]
        else:
            file_ext = os.path.splitext(original_filename)[1] or '.bin'
        
        remote_config_file = f"/tmp/modified{file_ext}"
        local_config_file = f"/tmp/config_{execution_id}{file_ext}"
        
        log_message(f"Original: {original_filename}")
        log_message(f"Extension: {file_ext}, Remote: {remote_config_file}")
        
        # Download file using wget (OpenWrt compatible)
        wget_cmd = [
            "wget",
            "-O", local_config_file,
            "--timeout=60",
            "--header=Accept-Encoding: identity",
            file_download_url
        ]
        
        result = subprocess.run(wget_cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"Download failed: {result.stderr}")
        
        file_size = os.path.getsize(local_config_file)
        log_message(f"Downloaded: {file_size} bytes")
        
        # Detect actual file type from magic bytes
        with open(local_config_file, 'rb') as f:
            magic = f.read(10)
        
        is_gzip = magic.startswith(b'\x1f\x8b')
        is_bzip2 = magic.startswith(b'BZ') or magic.startswith(b'\x42\x5a\x68')
        
        # Check for tar signature at offset 257
        with open(local_config_file, 'rb') as f:
            f.seek(257)
            tar_magic = f.read(5)
            is_tar = (tar_magic == b'ustar')
        
        log_message(f"Detection: gzip={is_gzip}, bzip2={is_bzip2}, tar={is_tar}")
        
        # ===== FIX TAR.GZ =====
        if file_ext == '.tar.gz':
            if is_gzip:
                try:
                    with tarfile.open(local_config_file, 'r:gz') as tar:
                        log_message(f"Valid tar.gz ({len(tar.getmembers())} files)")
                except:
                    raise Exception("Invalid tar.gz file")
            elif is_tar:
                log_message(f"Re-compressing plain tar to tar.gz...")
                temp_file = f"{local_config_file}.temp"
                with open(local_config_file, 'rb') as f_in:
                    with gzip.open(temp_file, 'wb', compresslevel=6) as f_out:
                        shutil.copyfileobj(f_in, f_out)
                os.replace(temp_file, local_config_file)
                log_message(f"Re-compressed: {file_size} → {os.path.getsize(local_config_file)} bytes")
            else:
                raise Exception("File is neither gzip nor tar")
        
        # ===== FIX TAR.BZ2 =====
        elif file_ext == '.tar.bz2':
            if is_bzip2:
                try:
                    with tarfile.open(local_config_file, 'r:bz2') as tar:
                        log_message(f"Valid tar.bz2 ({len(tar.getmembers())} files)")
                except:
                    raise Exception("Invalid tar.bz2 file")
            elif is_tar:
                log_message(f"Re-compressing plain tar to tar.bz2...")
                temp_file = f"{local_config_file}.temp"
                with open(local_config_file, 'rb') as f_in:
                    with bz2.open(temp_file, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                os.replace(temp_file, local_config_file)
                log_message(f"Re-compressed: {file_size} → {os.path.getsize(local_config_file)} bytes")
            else:
                raise Exception("File is neither bzip2 nor tar")
        
        # ===== FIX PLAIN .GZ =====
        elif file_ext == '.gz':
            if is_gzip:
                try:
                    with gzip.open(local_config_file, 'rb') as f:
                        f.read(100)
                    log_message(f"Valid .gz file")
                except:
                    raise Exception("Invalid .gz file")
            else:
                log_message(f"Compressing to .gz...")
                temp_file = f"{local_config_file}.temp"
                with open(local_config_file, 'rb') as f_in:
                    with gzip.open(temp_file, 'wb', compresslevel=6) as f_out:
                        shutil.copyfileobj(f_in, f_out)
                os.replace(temp_file, local_config_file)
                log_message(f"Compressed: {file_size} → {os.path.getsize(local_config_file)} bytes")
        
        # ===== FIX PLAIN .BZ2 =====
        elif file_ext == '.bz2':
            if is_bzip2:
                try:
                    with bz2.open(local_config_file, 'rb') as f:
                        f.read(100)
                    log_message(f"Valid .bz2 file")
                except:
                    raise Exception("Invalid .bz2 file")
            else:
                log_message(f"Compressing to .bz2...")
                temp_file = f"{local_config_file}.temp"
                with open(local_config_file, 'rb') as f_in:
                    with bz2.open(temp_file, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                os.replace(temp_file, local_config_file)
                log_message(f"Compressed: {file_size} → {os.path.getsize(local_config_file)} bytes")
        
        # ===== PLAIN TAR =====
        elif file_ext == '.tar':
            if not is_tar:
                raise Exception("Not a valid tar file")
            with tarfile.open(local_config_file, 'r:') as tar:
                log_message(f"Valid tar ({len(tar.getmembers())} files)")
        
        # ===== OTHER FILES =====
        else:
            log_message(f"Non-archive file, no compression needed")
        
        # Move to /tmp/ location
        log_message(f"Moving to {remote_config_file}...")
        shutil.move(local_config_file, remote_config_file)
        local_config_file = None  # Prevent cleanup
        
        # Verify file exists
        if os.path.exists(remote_config_file):
            file_size = os.path.getsize(remote_config_file)
            log_message(f"File ready: {remote_config_file} ({file_size} bytes)")
        
        # Verify integrity based on file type
        if file_ext == '.tar.gz':
            result = subprocess.run(
                f"tar -tzf {remote_config_file} 2>&1 | head -3",
                shell=True, capture_output=True, text=True
            )
            if 'invalid magic' in result.stdout or 'not in gzip format' in result.stdout:
                raise Exception(f"File corrupted: {result.stdout}")
            log_message(f"Verified tar.gz:\n{result.stdout}")
        
        elif file_ext == '.tar.bz2':
            result = subprocess.run(
                f"tar -tjf {remote_config_file} 2>&1 | head -3",
                shell=True, capture_output=True, text=True
            )
            if 'invalid' in result.stdout or 'corrupt' in result.stdout:
                raise Exception(f"File corrupted: {result.stdout}")
            log_message(f"Verified tar.bz2:\n{result.stdout}")
        
        elif file_ext == '.tar':
            result = subprocess.run(
                f"tar -tf {remote_config_file} 2>&1 | head -3",
                shell=True, capture_output=True, text=True
            )
            if 'invalid' in result.stdout or 'corrupt' in result.stdout:
                raise Exception(f"File corrupted: {result.stdout}")
            log_message(f"Verified tar:\n{result.stdout}")
        
        elif file_ext == '.gz':
            result = subprocess.run(
                f"gunzip -t {remote_config_file} 2>&1",
                shell=True, capture_output=True, text=True
            )
            if 'invalid' in result.stdout or 'not in gzip format' in result.stderr:
                raise Exception(f"File corrupted: {result.stdout} {result.stderr}")
            log_message(f"Verified .gz")
        
        elif file_ext == '.bz2':
            result = subprocess.run(
                f"bzip2 -t {remote_config_file} 2>&1",
                shell=True, capture_output=True, text=True
            )
            if 'invalid' in result.stdout or 'invalid' in result.stderr:
                raise Exception(f"File corrupted: {result.stdout} {result.stderr}")
            log_message(f"Verified .bz2")
        
        else:
            log_message(f"File uploaded (no verification needed for {file_ext})")
        
        return True, remote_config_file
        
    except Exception as error:
        import traceback
        traceback.print_exc()
        return False, str(error)
        
    finally:
        if local_config_file and os.path.exists(local_config_file):
            os.remove(local_config_file)
            log_message(f"Cleanup done")

# ===== MAIN FUNCTION =====
def mqtt_main():
    global mqtt_client
    logging.basicConfig(
        filename=CONFIG["LOG_FILE"],
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(message)s"
    )
    print("\n" + "="*70)
    log_message("UNIFIED MQTT AGENT STARTING")
    log_message(f"Device ID: {CONFIG['DEVICE_ID']}")
    log_message(f"Broker: {CONFIG['MQTT_BROKER_IP']}:{CONFIG['MQTT_BROKER_PORT']}")
    log_message(f"NB Command Topic: {TOPIC_CMD}")
    log_message(f"NB Response Topic: {TOPIC_RES}")
    log_message(f"Robot Command Topic: {COMMAND_TOPIC}")
    log_message(f"Robot Response Topic: {RESPONSE_TOPIC}")
    print("="*70 + "\n")









    client = mqtt.Client(client_id=f"device-{CONFIG['DEVICE_ID']}", protocol=mqtt.MQTTv311, clean_session=False)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    # Enable automatic reconnect
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    mqtt_client = client
    try:
        log_message(f"[Agent] Connecting to {CONFIG['MQTT_BROKER_IP']}:{CONFIG['MQTT_BROKER_PORT']} ...")
        client.connect(CONFIG["MQTT_BROKER_IP"], CONFIG["MQTT_BROKER_PORT"], keepalive=CONFIG["KEEPALIVE"])
        # Start worker thread
        threading.Thread(target=worker_thread, daemon=True).start()
        client.loop_forever()
    except Exception as e:
        log_message(f"[Agent] MQTT Connection error: {e}.")





if __name__ == "__main__":
    mqtt_main()