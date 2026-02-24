# START_DESCRIPTION
# 1. Setup MWAN3 bonding and resiliency policies for primary and backup interfaces.
# 2. Capture initial MWAN3 status to confirm primary link is active.
# 3. Trigger failover by disabling the primary interface.
# 4. Validate that backup interface takes over traffic at 100%.
# 5. Re-enable the primary interface and verify successful recovery.
# END_DESCRIPTION


#!/usr/bin/env python3
"""
WAN BONDING RESILIENCY  (BB-TRF-BND-003)
Dynamic target band input via command-line parameter
python3 BB_TRF_BND_003.py CONFIGURATION='{"primary_iface": "wan", "backup_iface":"wan2", "primary_weight":"1", "backup_weight":"1", "mode":"resiliency"}'
"""

import re
import sys
import time
import json
import argparse
import subprocess
from datetime import datetime
 
 
LOG_FILE = "BB_TRF_BND_003.log"
 
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
        # if output:
        #     log(f"[OUT]: {output}")
        if error:
            log(f"[ERR]: {error}")
        return output, error
    except Exception as e:
        log(f"Command execution failed: {e}")
        return "", str(e)

def setup_mwan3_complete( primary_iface="wan", backup_iface="wwan", primary_weight=1, backup_weight=3):
    
    log(f"[CONFIG]: Weights -> {primary_iface}: {primary_weight}, {backup_iface}: {backup_weight}")

    try:
        # STEP 0: Cleanup
        log("[STEP 0] Cleaning existing configuration")
        cleanup_items = [
            primary_iface, backup_iface, 
            f"m_{primary_iface}_b", f"m_{backup_iface}_b", 
            f"m_{primary_iface}_f", f"m_{backup_iface}_f", 
            "balanced", "wan_wanb", "default_rule"
        ]
        for item in cleanup_items:
            cmd = f"uci -q delete mwan3.{item}"
            log(f"[CMD] {cmd}")
            run_command(cmd)

        # STEP 1: Interface Tracking
        log("[STEP 1] Configuring Interface Tracking")
        # Define tracking parameters
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

        # STEP 2: Configure Members (Bonding vs Resiliency)
        log("[STEP 2] Configuring Members")
        
        member_configs = [
            # Bonding Members (Same Metric)
            (f"m_{primary_iface}_b", primary_iface, "1", primary_weight),
            (f"m_{backup_iface}_b", backup_iface, "1", backup_weight),
            # Resiliency Members (Different Metrics)
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

        # STEP 3: Create Policies
        log("[STEP 3] Creating Balanced and Resiliency Policies")
        policy_setup = [
            # Balanced Policy (Bonding)
            f"uci set mwan3.balanced='policy'",
            f"uci add_list mwan3.balanced.use_member='m_{primary_iface}_b'",
            f"uci add_list mwan3.balanced.use_member='m_{backup_iface}_b'",
            f"uci set mwan3.balanced.sticky='1'",
            
            # Resiliency Policy (Failover)
            f"uci set mwan3.wan_wanb='policy'",
            f"uci add_list mwan3.wan_wanb.use_member='m_{primary_iface}_f'",
            f"uci add_list mwan3.wan_wanb.use_member='m_{backup_iface}_f'",
            
            # Default Rule
            f"uci set mwan3.default_rule='rule'",
            "uci set mwan3.default_rule.dest_ip='0.0.0.0/0'",
            f"uci set mwan3.default_rule.use_policy='balanced'"
        ]
        for cmd in policy_setup:
            log(f"[CMD] {cmd}")
            run_command(cmd)

        # STEP 4: Apply
        log("[STEP 4] Committing and Restarting")
        for cmd in ["uci commit mwan3", "/etc/init.d/mwan3 restart"]:
            log(f"[CMD] {cmd}")
            run_command(cmd)

        log("========== SETUP COMPLETE ==========")
        return 0

    except Exception as e:
        log(f"ERROR: {str(e)}")
        raise

def verify_mwan3_resiliency_status(expected_primary, expected_backup, mode="resiliency"):
    policy_name = "balanced" if mode == "bonding" else "wan_wanb"

    try:
        def get_device(iface):
            cmd = f"ubus call network.interface.{iface} status"
            out, err = run_command(cmd)
            if not out:
                raise AssertionError(f"Could not get status for {iface}: {err}")
            data = json.loads(out)
            return data.get("l3_device") or data.get("device")

        dev1 = get_device(expected_primary)
        dev2 = get_device(expected_backup)

        log(f"{expected_primary} mapped to device: {dev1}")
        log(f"{expected_backup} mapped to device: {dev2}")

        def get_summary(status_text):
            summary = []
            summary.append("---------------- STATUS SUMMARY ----------------")
            for iface in [expected_primary, expected_backup]:
                match = re.search(rf"(interface {iface} is .*)", status_text)
                if match:
                    summary.append(f"  - {match.group(1)}")

            # policy_match = re.search(rf"{policy_name}:\n((?:\s+[^\n]+\n?)*)", status_text)
            policy_match = re.search(rf"{policy_name}:\n\s+([^\n]+)", status_text)
            if policy_match:
                summary.append(f"  - Policy '{policy_name}': -> {policy_match.group(1).strip()}")
                
            summary.append("------------------------------------------------")
            return "\n".join(summary)

        # PHASE 1 : INITIAL STATE 
        log("PHASE 1 : INITIAL STATE ")
      
        status_1, _ = run_command("mwan3 status")
        log(get_summary(status_1))
        
        if f"{expected_primary} (100%)" not in status_1:
            raise AssertionError(f"Pre-test Failure: {expected_primary} is not active at 100%")

        # PHASE 2 : FAILOVER 
        log("PHASE 2 : FAILOVER ")
        log(f"ACTION: Bringing down {expected_primary} ({dev1})")
        run_command(f"ip link set {dev1} down")
        
        log("Waiting 10 seconds for mwan3 to detect link down...")
        time.sleep(10) 

        status_2, _ = run_command("mwan3 status")
        log(get_summary(status_2))

        if f"{expected_backup} (100%)" not in status_2:
            raise AssertionError(f"Failover Failure: {expected_backup} did not take over at 100%")

        # PHASE 3 : RECOVERY
        log("PHASE 3 : RECOVERY ")
        log(f"ACTION: Restoring {expected_primary} ({dev1})")
        run_command(f"ip link set {dev1} up")
        
        log("Waiting 10 seconds for mwan3 to recover...")
        time.sleep(10)

        status_3, _ = run_command("mwan3 status")
        log(get_summary(status_3))

        if f"{expected_primary} (100%)" not in status_3:
            raise AssertionError(f"Recovery Failure: {expected_primary} did not regain 100% control")

        log(f"========== MWAN3 ({mode.upper()}) VERIFICATION PASSED ==========")
        return True

    except Exception as e:
        log(f"ERROR: {str(e)}")
        run_command(f"ip link set {dev1} up")
        raise e

    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='WAN BONDING RESILIENCY (BB-TRF-BND-003)')
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
        # Step 1: Configuration
        log(f"\n========== CONFIGURATION ==========")
        setup_mwan3_complete(PRIMARY_IFACE, BACKUP_IFACE, PRIMARY_WEIGHT, BACKUP_WEIGHT)
        
        # Give mwan3 a few seconds to start tracking before verifying
        log("Waiting 5 seconds for mwan3 to initialize tracking...")
        time.sleep(5)
         
        # Step 2: Verification
        log(f"\n========== VERIFYING MWAN3 ({MODE.upper()}) ==========")
        success = verify_mwan3_resiliency_status(PRIMARY_IFACE, BACKUP_IFACE, MODE)
        
        if success:
            log("\n[RESULT]: PASSED")
            sys.exit(0)
        
    except Exception as e:
        log(f"Detailed Error: {e}")
        log("\n[RESULT]: FAILED")
        sys.exit(1)