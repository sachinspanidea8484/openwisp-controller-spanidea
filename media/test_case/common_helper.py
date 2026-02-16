"""
Common Helper for NBAPI Testcases
"""
import os
import sys
import json
import subprocess
from datetime import datetime

EXIT_SUCCESS = 0
EXIT_FAILED = 1

def log(message, *args, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if args:
        try:
            message = message % args
        except Exception:
            message = f"{message} {args}"
    print(f"{timestamp} [{level}] {message}")

def run_local_command(command, check=True, capture_output=True, text=True, shell=True, allow_fail=False):
    log("Executing command: %s", command)
    try:
        result = subprocess.run(command, shell=shell, capture_output=capture_output, text=text, check=check)
        return (result.stdout.strip() if result.stdout else "",
                result.stderr.strip() if result.stderr else "",
                result.returncode)
    except subprocess.CalledProcessError as e:
        if not allow_fail:
            log("Command failed (RC=%d): %s", e.returncode, command, level="FAIL")
            raise
        return ("", e.stderr.strip() if e.stderr else "", e.returncode)

def verify_file_exists(filepath):
    if not os.path.isfile(filepath):
        log("File not found: %s", filepath, level="FAIL")
        return False
    log("Verified file exists: %s", filepath, level="PASS")
    return True

def parse_configuration(config_str):
    if not config_str:
        log("Empty CONFIGURATION argument", level="FAIL")
        sys.exit(EXIT_FAILED)
    if config_str.startswith("CONFIGURATION"):
        config_str = config_str.split("=", 1)[-1]
    try:
        return json.loads(config_str)
    except json.JSONDecodeError as e:
        log("Invalid CONFIGURATION JSON: %s", e, level="FAIL")
        sys.exit(EXIT_FAILED)

def get_up_interfaces():
    stdout, _, _ = run_local_command("ip -o addr show | grep -v lo | awk '{print $2}' | sort -u", allow_fail=True)
    return stdout.split() if stdout else []

def update_rc_local(script_path, config_str):
    exec_line = f"python3 {script_path} 'REBOOT_CONTEXT CONFIGURATION={config_str}'"
    if not os.path.exists("/etc/rc.local"):
        with open("/etc/rc.local", "w") as f:
            f.write("#!/bin/sh -e\n\nexit 0\n")
    with open("/etc/rc.local", "r") as f:
        lines = f.readlines()
    if any(script_path in line for line in lines):
        log("rc.local already contains entry for %s", script_path)
        return
    with open("/etc/rc.local", "w") as f:
        for line in lines:
            if line.strip() == "exit 0":
                f.write(f"{exec_line}\n")
            f.write(line)
    log("Added reboot hook to rc.local for %s", script_path, level="PASS")

def clear_rc_local(script_path):
    if not os.path.exists("/etc/rc.local"):
        return
    with open("/etc/rc.local", "r") as f:
        lines = f.readlines()
    with open("/etc/rc.local", "w") as f:
        for line in lines:
            if script_path not in line:
                f.write(line)
    log("Removed rc.local entry for %s", script_path, level="PASS")

def extract_target_block(output, target_sensor):
    lines = output.splitlines()
    block = []
    inside_target = False
    for line in lines:
        if target_sensor in line:
            inside_target = True
            block.append(line)
            continue
        if inside_target:
            if line.strip() == "":
                break
            block.append(line)
    return "\n".join(block)

def parse_sensor_output(block):
    voltage = None
    current = None
    for line in block.splitlines():
        if "Bus Voltage" in line:
            try:
                voltage = float(line.split(":")[1].strip())
            except Exception:
                pass
        elif "Current (A)" in line:
            try:
                current = float(line.split(":")[1].strip())
            except Exception:
                pass
    return voltage, current

