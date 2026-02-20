"""
SD Card Slot Verification Test using common_helper.py
"""

import sys
import time
from common_helper import log, logf, run_local_command, EXIT_SUCCESS, EXIT_FAILED

# ======================
# SD CARD OPERATIONS
# ======================
def check_sdcard_present():
    stdout, _, rc = run_local_command("ls /dev/mmcblk* 2>/dev/null", allow_fail=True)
    return rc == 0 and stdout != ""

def mount_sdcard():
    run_local_command("mkdir -p /mnt/sdcard", allow_fail=True)
    _, _, rc = run_local_command("mount /dev/mmcblk0p1 /mnt/sdcard", allow_fail=True)
    return rc == 0

def verify_mount():
    stdout, _, rc = run_local_command("mount | grep /mnt/sdcard", allow_fail=True)
    return rc == 0

def write_test_file():
    _, _, rc = run_local_command('echo "SD Card Automation Test" > /mnt/sdcard/sd_test.txt', allow_fail=True)
    return rc == 0

def read_test_file():
    stdout, _, rc = run_local_command("cat /mnt/sdcard/sd_test.txt", allow_fail=True)
    return rc == 0 and "SD Card Automation Test" in stdout

def delete_test_file():
    _, _, rc = run_local_command("rm -f /mnt/sdcard/sd_test.txt", allow_fail=True)
    if rc != 0:
        return False
    stdout, _, rc = run_local_command("ls /mnt/sdcard | grep sd_test.txt", allow_fail=True)
    return rc != 0  # file should NOT exist

def unmount_sdcard():
    _, _, rc = run_local_command("umount /mnt/sdcard", allow_fail=True)
    return rc == 0

# ======================
# MAIN TEST ENTRY POINT
# ======================
def run_test():
    log("=== BB-SU-008 : SD Card Slot Verification ===")
    
    # Step 1: Detect SD Card
    if not check_sdcard_present():
        log("[FAIL] SD card not detected.")
        return EXIT_FAILED
    log("[INFO] SD card detected.")
    
    # Step 2: Mount
    if not mount_sdcard():
        log("[FAIL] SD card mount failed.")
        return EXIT_FAILED
    
    if not verify_mount():
        log("[FAIL] SD card not mounted.")
        return EXIT_FAILED
    log("[INFO] SD card mounted.")
    
    # Step 3: Write
    if not write_test_file():
        log("[FAIL] Failed to write test file.")
        return EXIT_FAILED
    log("[INFO] Write successful.")
    
    # Step 4: Read
    if not read_test_file():
        log("[FAIL] Failed to read or verify test file.")
        return EXIT_FAILED
    log("[INFO] Read successful.")
    
    # Step 5: Delete
    if not delete_test_file():
        log("[FAIL] Failed to delete test file.")
        return EXIT_FAILED
    log("[INFO] Delete successful.")
    
    # Step 6: Unmount
    if not unmount_sdcard():
        log("[FAIL] Failed to unmount SD card.")
        return EXIT_FAILED
    log("[INFO] SD card unmounted.")
    
    log("[PASS] Testcase Passed successfully")
    return EXIT_SUCCESS

if __name__ == "__main__":
    exit_code = run_test()
    sys.exit(exit_code)

