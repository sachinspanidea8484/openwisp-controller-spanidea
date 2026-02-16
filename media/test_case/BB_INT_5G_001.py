#START_DESCRIPTION 
#1. Initialize logging
#2. Attach the DUT to the 5G network and verify.
#3. Check the DUT connection, signal information.
#4. Verify connectivity by ping from DUT to PC (remote=8.8.8.8)
# END_DESCRIPTION



#!/usr/bin/env python3
"""
5G WAN INTERFACE TEST (BB-INT-5G-001)
Dynamic target band input via command-line parameter
python3 BB_INT_5G_001.py CONFIGURATION='{"cellular_interface": "Modem1", "remote_ping_ip": "8.8.8.8", "test_duration" : "60", "error_threshold_percent":"10"}'
"""


import re
import sys
import time
import json
import argparse
from datetime import datetime
from common_helper import (log, run_local_command, parse_config, get_modem_status, ensure_modem_connected, validate_ifconfig_errors, EXIT_SUCCESS,EXIT_FAILED)



#CONSTANTS
MAX_RETRIES = 3
EXIT_SUCCESS = 0
EXIT_FAILED = 1


    
def ping_remote(iface, remote_ip):
    log("Pinging %s via %s...", remote_ip, iface)

    stdout, stderr, rc = run_local_command(f"ping -I {iface} -c 4 {remote_ip}",allow_fail=True)

    # Print full ping output
    if stdout:
        log("Ping Output:\n%s", stdout)

    if rc != 0 or "100% packet loss" in stdout or "0 received" in stdout:
        log("Ping failed.", level="ERROR")
        return False

    log("Ping successful.")
    return True

   
# === MAIN LOGIC ===
if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='5G WAN INTERFACE (BB-INT-5G-001)')
    parser.add_argument('config', help='Configuration string')
    args = parser.parse_args()

    config = parse_config(args.config)

    CELLULAR_IFACE = config.get('cellular_interface', 'Modem1')
    REMOTE_PING_IP = config.get('remote_ping_ip', '8.8.8.8')
    TEST_DURATION = int(config.get('test_duration', 60))
    THRESHOLD = float(config.get('error_threshold_percent', 10))

    log("Starting 5G WAN Interface Test BB-INT-5G-001...")

    try:
        info = get_modem_status(CELLULAR_IFACE)

        if not info:
            log("TEST FAILED - Failed to get modem status", level="ERROR")
            sys.exit(EXIT_FAILED)

        QMI_DEVICE = info["qmi_device"]
        DATA_INTERFACE = info["data_interface"]
        NETWORK_TYPE = info["network_type"]
        log("Modem Info - QMI Device: %s | Data Interface: %s | Network Type: %s",QMI_DEVICE, DATA_INTERFACE, NETWORK_TYPE)

        if not ensure_modem_connected(CELLULAR_IFACE, QMI_DEVICE):
            log("TEST FAILED - Modem failed to connect", level="ERROR")
            sys.exit(EXIT_FAILED)

        if NETWORK_TYPE != "5G":
            log("TEST FAILED - %s is not a 5G WAN interface but has %s",
            CELLULAR_IFACE, NETWORK_TYPE, level="ERROR")
            sys.exit(EXIT_FAILED)

      
        if not ping_remote(DATA_INTERFACE, REMOTE_PING_IP):
            log("TEST FAILED - Initial connectivity check failed", level="ERROR")
            sys.exit(EXIT_FAILED)

        
        log("Initial connectivity check PASSED: %s via %s .",NETWORK_TYPE, DATA_INTERFACE)

        # Stability Test
        log("Starting %d seconds stability test...", TEST_DURATION)

        start = time.time()

        while time.time() - start < TEST_DURATION:
            if not ping_remote(DATA_INTERFACE, REMOTE_PING_IP):
                log("TEST FAILED - Ping failed during stability test", level="ERROR")
                sys.exit(EXIT_FAILED)
            time.sleep(30)

        log("TEST PASSED - Stability test completed successfully for %d seconds",
            TEST_DURATION)
        
        # Validate interface errors
        if not validate_ifconfig_errors(DATA_INTERFACE, THRESHOLD):
            sys.exit(EXIT_FAILED)

        log("TEST PASSED - Stability and IFCONFIG validation successful")
        sys.exit(EXIT_SUCCESS)

    except Exception as e:
        log("TEST FAILED - Unhandled exception: %s", e, level="ERROR")
        sys.exit(EXIT_FAILED)
