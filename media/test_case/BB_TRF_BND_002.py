# START_DESCRIPTION
# 1. Setup MWAN3 bonding with 2 or 3 WAN interfaces.
# 2. Check all interfaces are online and tracked.
# 3. Run "mwan3 status".
# 4. Verify policy distribution percentages match configured weights.
# END_DESCRIPTION


#!/usr/bin/env python3
"""
WAN BONDING 4G/5G and WWAN  (BB-TRF-BND-002)
Dynamic target band input via command-line parameter
python3 BB_TRF_BND_002.py CONFIGURATION='{"primary_iface":"wan","backup_iface":"wan2","tertiary_iface":"wan3","primary_weight":"1","backup_weight":"1","tertiary_weight":"1", "mode":"bonding"}'
"""

import re
import sys
import time
import json
import argparse
import subprocess
from datetime import datetime
 
 
LOG_FILE = "BB_TRF_BND_002.log"
 
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
    log(f"[CMD] {cmd}")
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

def setup_mwan3_complete(
    primary_iface="wan",
    backup_iface="wwan",
    tertiary_iface="eth1",
    p_weight=1,
    b_weight=1,
    t_weight=1
):
    log(f"[CONFIG]: Primary iface : Weights -> {primary_iface}: {p_weight}")
    log(f"[CONFIG]: Backup ifcae : Weights -> {backup_iface}: {b_weight}")
    log(f"[CONFIG]: Teritiary iface : Weights -> {tertiary_iface}: {t_weight}")

    try:
        # STEP 0: Comprehensive Cleanup
        log("[STEP 0] Backing up current mwan3 config")

        backup_cmd = "cp /etc/config/mwan3 /etc/config/mwan3.backup"
        log(f"[CMD] {backup_cmd}")
        run_command(backup_cmd)
        
        log("[STEP 0] Cleaning existing configuration for 3 interfaces")
       
        ifaces = [primary_iface, backup_iface, tertiary_iface]
        cleanup_items = ["balanced", "wan_wanb", "default_rule"]
        
        for iface in ifaces:
            cleanup_items.extend([iface, f"m_{iface}_b", f"m_{iface}_f"])
            
        for item in cleanup_items:
            cmd = f"uci -q delete mwan3.{item}"
            run_command(cmd)

        # STEP 1: Interface Tracking (3-Way)
        log("[STEP 1] Configuring Interface Tracking for 3 Links")
        track_configs = [
            (primary_iface, ["8.8.8.8", "1.1.1.1"]),
            (backup_iface, ["8.8.4.4", "9.9.9.9"]),
            (tertiary_iface, ["208.67.222.222", "1.0.0.1"]) # OpenDNS/Cloudflare
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
                run_command(cmd)

        # STEP 2: Configure Members (Bonding vs Tiered Resiliency)
        log("[STEP 2] Configuring Members (Bonding and Tiered Failover)")
        
        member_configs = [
            # Bonding Members (Metric 1 for simultaneous use)
            (f"m_{primary_iface}_b", primary_iface, "1", p_weight),
            (f"m_{backup_iface}_b", backup_iface, "1", b_weight),
            (f"m_{tertiary_iface}_b", tertiary_iface, "1", t_weight),
            
            # Tiered Resiliency Members (Metric 1 -> 2 -> 3)
            (f"m_{primary_iface}_f", primary_iface, "1", "1"),
            (f"m_{backup_iface}_f", backup_iface, "2", "1"),
            (f"m_{tertiary_iface}_f", tertiary_iface, "3", "1")
        ]

        for m_name, iface, metric, weight in member_configs:
            cmds = [
                f"uci set mwan3.{m_name}='member'",
                f"uci set mwan3.{m_name}.interface='{iface}'",
                f"uci set mwan3.{m_name}.metric='{metric}'",
                f"uci set mwan3.{m_name}.weight='{weight}'"
            ]
            for cmd in cmds:
                run_command(cmd)

        # STEP 3: Create Policies
        log("[STEP 3] Creating Triple-Link Policies")
        policy_setup = [
            # Balanced Policy (Bonding all 3)
            "uci set mwan3.balanced='policy'",
            f"uci add_list mwan3.balanced.use_member='m_{primary_iface}_b'",
            f"uci add_list mwan3.balanced.use_member='m_{backup_iface}_b'",
            f"uci add_list mwan3.balanced.use_member='m_{tertiary_iface}_b'",
            "uci set mwan3.balanced.sticky='1'",
            
            # Resiliency Policy (Failover Order: Primary > Backup > Tertiary)
            "uci set mwan3.wan_wanb='policy'",
            f"uci add_list mwan3.wan_wanb.use_member='m_{primary_iface}_f'",
            f"uci add_list mwan3.wan_wanb.use_member='m_{backup_iface}_f'",
            f"uci add_list mwan3.wan_wanb.use_member='m_{tertiary_iface}_f'",
            
            # Default Rule
            "uci set mwan3.default_rule='rule'",
            "uci set mwan3.default_rule.dest_ip='0.0.0.0/0'",
            "uci set mwan3.default_rule.use_policy='balanced'"
        ]
        for cmd in policy_setup:
            run_command(cmd)

        # STEP 4: Apply
        log("[STEP 4] Committing and Restarting")
        for cmd in ["uci commit mwan3", "/etc/init.d/mwan3 restart"]:
            run_command(cmd)

        log("========== MWAN3 SETUP COMPLETE ==========")
        return 0

    except Exception as e:
        log(f"ERROR: {str(e)}")
        raise
    

def verify_mwan3_bonding_status(
        primary_iface="wan",
        backup_iface="wan2",
        tertiary_iface="none",
        p_weight=1,
        b_weight=1,
        t_weight=0,
        mode="bonding"):

    policy_name = "balanced" if mode == "bonding" else "wan_wanb"

    try:
        # Build interface & weight lists dynamically
        iface_list = [primary_iface, backup_iface]
        weight_list = [int(p_weight), int(b_weight)]
        
        if tertiary_iface:
            iface_list.append(tertiary_iface)
            weight_list.append(int(t_weight))

        total_weight = sum(weight_list)
        percent_list = [round((w / total_weight) * 100) for w in weight_list]

        def get_summary(status_text):
            summary = []
            summary.append("---------------- STATUS SUMMARY ----------------")

            for iface in iface_list:
                match = re.search(rf"(interface {iface} is .*)", status_text)
                if match:
                    summary.append(f"  - {match.group(1)}")

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

        # STEP 1: Fetch MWAN3 status
        log("[STEP 1] Fetching MWAN3 status")
        status_output, status_error = run_command("mwan3 status")
        
        if not status_output and status_error:
             raise AssertionError(f"mwan3 status command failed: {status_error}")
         
        log(get_summary(status_output))

        # STEP 2: Check Interface Online
        log("[STEP 2] Checking Interface Status")

        for iface in iface_list:
            pattern = rf"interface {iface} is online and tracking is active"
            if not re.search(pattern, status_output):
                raise AssertionError(f"{iface} is not online and tracking active!")

        log(f"SUCCESS: All interfaces {iface_list} are ONLINE and Tracking.")

        # STEP 3: Check Policy Distribution
        log("[STEP 3] Checking Policy Distribution")

        # policy_match = re.search(rf"{policy_name}:\n\s+([^\n]+)", status_output)
        policy_match = re.search(rf"{policy_name}:\n((?:\s+[^\n:]+.*\n?)*)", status_output)
        if not policy_match:
            raise AssertionError(f"Could not find '{policy_name}' policy distribution line.")

        policy_line = policy_match.group(1).strip()

        # Build expected checks dynamically
        expected_checks = []
        for iface, percent in zip(iface_list, percent_list):
            expected_checks.append(f"{iface} ({percent}%)")

        for check in expected_checks:
            if check not in policy_line:
                raise AssertionError(
                    f"Weight Mismatch! Expected {expected_checks}, but found: {policy_line}"
                )

        log(f"SUCCESS: Policy '{policy_name}' verified with {expected_checks}")

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
    parser = argparse.ArgumentParser(description='WAN BONDING 4G/5G and WWAN (BB-TRF-BND-002)')
    parser.add_argument('config', help='Configuration string')
 
    args = parser.parse_args()
    config = parse_config(args.config)
 
    PRIMARY_IFACE = config.get('primary_iface', 'wan')    
    BACKUP_IFACE = config.get('backup_iface', 'Modem1') 
    TERTIARY_IFACE= config.get('tertiary_iface', 'wwan') 
    PRIMARY_WEIGHT = config.get('primary_weight', '1')  
    BACKUP_WEIGHT = config.get('backup_weight', '1')  
    TERTIARY_WEIGHT = config.get('tertiary_weight', '1')  
    MODE = config.get('mode', 'bonding')  
    
    log(f"=== Starting WAN Bonding Setup ===")
    
    try:
        # Step 1: Configuration
        log(f"\n========== CONFIGURATION ==========")
        setup_mwan3_complete(PRIMARY_IFACE, BACKUP_IFACE, TERTIARY_IFACE, PRIMARY_WEIGHT, BACKUP_WEIGHT, TERTIARY_WEIGHT)
        
        # Give mwan3 a few seconds to start tracking before verifying
        log("Waiting 5 seconds for mwan3 to initialize tracking...")
        time.sleep(5)
         
        # Step 2: Verification
        log(f"\n========== VERIFYING MWAN3 ({MODE.upper()}) ==========")
        success = verify_mwan3_bonding_status(PRIMARY_IFACE, BACKUP_IFACE, TERTIARY_IFACE, PRIMARY_WEIGHT, BACKUP_WEIGHT, TERTIARY_WEIGHT, MODE)
        
        if success:
            log("\n[RESULT]: PASSED")
            sys.exit(0)
        
    except Exception as e:
        log(f"Detailed Error: {e}")
        log("\n[RESULT]: FAILED")
        sys.exit(1)
        
    finally:
        # Always restore config
        restore_mwan3()    