# START_DESCRIPTION
# 1. Setup MWAN3 bonding policy for primary and backup WAN interfaces.
# 2. Verify both links are online and tracking is active.
# 3. Check balanced policy distributes traffic based on configured weights.
# 4. Validate successful 4G/5G WAN bonding.
# END_DESCRIPTION



#!/usr/bin/env python3
"""
WAN BONDING 4G/5G  (BB-TRF-BND-001)
Dynamic target band input via command-line parameter
python3 BB_TRF_BND_001.py CONFIGURATION='{"primary_iface": "waneth1", "backup_iface":"wan1", "primary_weight":"1", "backup_weight":"1", "mode":"bonding"}'
"""

import re
import sys
import time
import json
import argparse
import subprocess
from datetime import datetime
 
 
LOG_FILE = "BB_TRF_BND_001.log"
 
def parse_config(config_str):
    """Parse CONFIGURATION=... style string into a Python dict"""
 
    # Remove 'CONFIGURATION=' prefix if present
    if config_str.startswith("CONFIGURATION="):
        config_str = config_str[len("CONFIGURATION="):]
 
    # Try to parse the remaining string as JSON
    try:
        return json.loads(config_str)
    except json.JSONDecodeError as e:
        print(f"Error parsing CONFIGURATION JSON: {e}", file=sys.stderr)
        return {}

# === LOGGING ===
def timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log(message):
    line = f"[+] {timestamp()} - {message}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

# === SHELL HELPER ===
def run_command(cmd):
    # log(f"[CMD] {cmd}")
    try:        
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=20 )

        output = result.stdout.strip()
        error = result.stderr.strip()
        if output:
            log(f"[OUT]: {output}")
        if error:
            log(f"[ERR]: {error}")
        return output, error
    except Exception as e:
        log(f"Command execution failed: {e}")
        return "", str(e)

def setup_mwan3_complete( primary_iface="wan", backup_iface="wwan", primary_weight=1, backup_weight=3):
    
    log(f"[CONFIG]: Weights -> {primary_iface}: {primary_weight}, {backup_iface}: {backup_weight}")
  
    try:
        
        log("[STEP 0] Backing up current mwan3 config")

        backup_cmd = "cp /etc/config/mwan3 /etc/config/mwan3.backup"
        log(f"[CMD] {backup_cmd}")
        run_command(backup_cmd)
        
        # STEP 0: Cleanup ONLY members and policy use_member lists
        log("[STEP 0] Cleaning existing members and policy member lists")

        member_items = [
            primary_iface,
            backup_iface, 
            f"m_{primary_iface}_b",
            f"m_{backup_iface}_b",
            f"m_{primary_iface}_f",
            f"m_{backup_iface}_f"
        ]

        for item in member_items:
            cmd = f"uci -q delete mwan3.{item}"
            log(f"[CMD] {cmd}")
            run_command(cmd)

        # Clear old use_member lists (do NOT delete policies)
        clear_policy_cmds = [
            "uci -q delete mwan3.balanced.use_member",
            "uci -q delete mwan3.wan_wanb.use_member"
        ]

        for cmd in clear_policy_cmds:
            log(f"[CMD] {cmd}")
            run_command(cmd)

        # STEP 1: Interface Tracking
        log("[STEP 1] Configuring Interface Tracking")

        track_configs = [
            (primary_iface, ["8.8.8.8", "1.1.1.1"]),
            (backup_iface, ["8.8.4.4", "9.9.9.9"])
        ]

        for iface, ips in track_configs:
            cmds = [
                f"uci set mwan3.{iface}='interface'",
                f"uci set mwan3.{iface}.enabled='1'",
                f"uci set mwan3.{iface}.family='ipv4'",
                f"uci set mwan3.{iface}.interval='2'",
                f"uci set mwan3.{iface}.down='3'"
            ]
            for ip in ips:
                cmds.append(f"uci add_list mwan3.{iface}.track_ip='{ip}'")

            for cmd in cmds:
                log(f"[CMD] {cmd}")
                run_command(cmd)

        # STEP 2: Configure Members
        log("[STEP 2] Configuring Members")

        member_configs = [
            (f"m_{primary_iface}_b", primary_iface, "1", primary_weight),
            (f"m_{backup_iface}_b", backup_iface, "1", backup_weight),
            (f"m_{primary_iface}_f", primary_iface, "1", "1"),
            (f"m_{backup_iface}_f", backup_iface, "2", "1")
        ]

        for m_name, iface, metric, weight in member_configs:
            cmds = [
                f"uci set mwan3.{m_name}='member'",
                f"uci set mwan3.{m_name}.interface='{iface}'",
                f"uci set mwan3.{m_name}.metric='{metric}'",
                f"uci set mwan3.{m_name}.weight='{weight}'"
            ]
            for cmd in cmds:
                log(f"[CMD] {cmd}")
                run_command(cmd)

        # STEP 3: Attach members to existing policies
        log("[STEP 3] Updating Policies")

        policy_setup = [
            # Balanced policy
            f"uci add_list mwan3.balanced.use_member='m_{primary_iface}_b'",
            f"uci add_list mwan3.balanced.use_member='m_{backup_iface}_b'",
            f"uci set mwan3.balanced.sticky='1'",

            # Failover policy
            f"uci add_list mwan3.wan_wanb.use_member='m_{primary_iface}_f'",
            f"uci add_list mwan3.wan_wanb.use_member='m_{backup_iface}_f'",

            # Default rule
            f"uci set mwan3.default_rule='rule'",
            "uci set mwan3.default_rule.dest_ip='0.0.0.0/0'",
            "uci set mwan3.default_rule.use_policy='balanced'"
        ]

        for cmd in policy_setup:
            log(f"[CMD] {cmd}")
            run_command(cmd)

        # STEP 4: Apply
        log("[STEP 4] Commit and Restart MWAN3")

        for cmd in ["uci commit mwan3", "/etc/init.d/mwan3 restart"]:
            log(f"[CMD] {cmd}")
            run_command(cmd)

        log("========== MWAN3 SETUP COMPLETE ==========")
        return 0

    except Exception as e:
        log(f"ERROR: {str(e)}")
        raise


def verify_mwan3_bonding_status(expected_primary="wan", expected_backup="wwan", p_weight=1, b_weight=1, mode = "bonding"):
    policy_name = "balanced" if mode == "bonding" else "wan_wanb"

    try:
        
        total = int(p_weight) + int(b_weight)
        p_percent = round((int(p_weight) / total) * 100)
        b_percent = round((int(b_weight) / total) * 100)
        def get_summary(status_text):
            summary = []
            summary.append("---------------- STATUS SUMMARY ----------------")

            for iface in [expected_primary, expected_backup]:
                match = re.search(rf"(interface {iface} is .*)", status_text)
                if match:
                    summary.append(f"  - {match.group(1)}")

            # Capture only the balanced policy block (not other policies)
            policy_match = re.search(
                rf"{policy_name}:\n((?:\s+[^\n:]+.*\n?)*)",
                status_text
            )

            if policy_match:
                summary.append(f"  - Policy '{policy_name}':")
                for line in policy_match.group(1).strip().splitlines():
                    summary.append(f"      {line.strip()}")

            summary.append("-----------------------------------------")
            return "\n".join(summary)

        #  STEP 1: Get MWAN3 status
        log("[STEP 1] Fetching MWAN3 status")
        status_output, status_error = run_command("mwan3 status")
        
        if not status_output and status_error:
             raise AssertionError(f"mwan3 status command failed: {status_error}")

        log(status_output)
        log(get_summary(status_output))

        # STEP 2: Check Interface Online
        log("[STEP 2] Checking Interface Status")

        wan_pattern = rf"interface {expected_primary} is online and tracking is active"
        wwan_pattern = rf"interface {expected_backup} is online and tracking is active"

        if not re.search(wan_pattern, status_output):
            raise AssertionError(f"{expected_primary} is not online and tracking active!")

        if not re.search(wwan_pattern, status_output):
            raise AssertionError(f"{expected_backup} is not online and tracking active!")

        log(f"SUCCESS: Both {expected_primary} and {expected_backup} are ONLINE and Tracking.")

       # STEP 3: Check Policy Distribution
        log("[STEP 3] Checking Policy Distribution")

        # policy_match = re.search(rf"{policy_name}:\n\s+([^\n]+)", status_output)
        policy_match = re.search(rf"{policy_name}:\n((?:\s+[^\n:]+.*\n?)*)", status_output)
        if not policy_match:
            raise AssertionError(f"Could not find '{policy_name}' policy distribution line.")

        policy_line = policy_match.group(1).strip()

        check_p = f"{expected_primary} ({p_percent}%)"
        check_b = f"{expected_backup} ({b_percent}%)"

        if check_p in policy_line and check_b in policy_line:
            log(f"SUCCESS: Policy '{policy_name}' verified with {check_p} and {check_b}")
        else:
            raise AssertionError(
                f"Weight Mismatch! Expected {check_p} and {check_b}, but found: {policy_line}"
            )
        
        log("========== BONDING VERIFICATION PASSED ==========")
        
        return True

    except AssertionError as ae:
        log("========== BONDING VERIFICATION FAILED ==========")
        log(f"ASSERTION ERROR: {str(ae)}")
        raise

    except Exception as e:
        log("========== BONDING VERIFICATION FAILED ==========")
        log(f"UNEXPECTED ERROR: {str(e)}")
        raise AssertionError(f"MWAN3 bonding verification failed due to exception: {str(e)}")
    

    
def restore_mwan3():
    log("========== RESTORE MWAN3 ==========")

    try:
        backup_file = "/etc/config/mwan3.backup"

        # Check backup exists
        run_command(f"test -f {backup_file}")

        log("[STEP 1] Restoring MWAN3 config from backup")
        run_command(f"cp {backup_file} /etc/config/mwan3")

        log("[STEP 2] Commit and Restart MWAN3")
        run_command("uci commit mwan3")
        run_command("/etc/init.d/mwan3 restart")

        log("========== RESTORE COMPLETE ==========")

    except Exception as e:
        log(f"ERROR during restore: {e}")
      
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='WAN BONDING 4G/5G (BB-TRF-BND-001)')
    parser.add_argument('config', help='Configuration string')
 
    args = parser.parse_args()
    config = parse_config(args.config)
 
    PRIMARY_IFACE = config.get('primary_iface', 'wan')    
    BACKUP_IFACE = config.get('backup_iface', 'Modem1') 
    PRIMARY_WEIGHT = config.get('primary_weight', '1')  
    BACKUP_WEIGHT = config.get('backup_weight', '1')  
    MODE = config.get('mode', 'bonding')  
    
    log(f"=== Starting WAN Bonding Setup ===")
    
    try:
        log(f"\n========== CONFIGURATION ==========")
        setup_mwan3_complete(PRIMARY_IFACE, BACKUP_IFACE, PRIMARY_WEIGHT, BACKUP_WEIGHT)

        log("Waiting 5 seconds for mwan3 to initialize tracking...")
        time.sleep(5)

        log(f"\n========== VERIFYING MWAN3 ({MODE.upper()}) ==========")
        success = verify_mwan3_bonding_status(
            PRIMARY_IFACE, BACKUP_IFACE, PRIMARY_WEIGHT, BACKUP_WEIGHT, MODE
        )

        if success:
            log("\n[RESULT]: PASSED")
            sys.exit(0)
        else:
            raise Exception("Verification failed")

    except Exception as e:
        log(f"Detailed Error: {e}")
        log("\n[RESULT]: FAILED")
        sys.exit(1)

    finally:
        # Always restore config
        restore_mwan3()

