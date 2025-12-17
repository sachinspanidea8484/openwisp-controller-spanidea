import subprocess
import sys
from datetime import datetime
 
EXIT_SUCCESS = 0
EXIT_FAILED = 1
 
def log(msg):
    timestamp = datetime.now().strftime("[%Y%m%d-%H%M%S]")
    print(f"{timestamp} {msg}", flush=True)
 
def run_cmd(cmd):
    """Run a shell command and return (stdout, stderr, returncode)."""
    try:
        result = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        out, err = result.communicate(timeout=10)
        return out.strip(), err.strip(), result.returncode
    except Exception as e:
        return "", str(e), 1
 
 
# ======================
# SD CARD OPERATIONS
# ======================
 
def check_sdcard_present():
    out, err, rc = run_cmd("ls /dev/mmcblk* 2>/dev/null")
    return rc == 0 and out != ""
 
def mount_sdcard():
    run_cmd("mkdir -p /mnt/sdcard")
    out, err, rc = run_cmd("mount /dev/mmcblk0p1 /mnt/sdcard")
    return rc == 0
 
def verify_mount():
    out, err, rc = run_cmd("mount | grep /mnt/sdcard")
    return rc == 0
 
def write_test_file():
    out, err, rc = run_cmd(
        'echo "SD Card Automation Test" > /mnt/sdcard/sd_test.txt'
    )
    return rc == 0
 
def read_test_file():
    out, err, rc = run_cmd("cat /mnt/sdcard/sd_test.txt")
    return rc == 0 and "SD Card Automation Test" in out
 
def delete_test_file():
    out, err, rc = run_cmd("rm -f /mnt/sdcard/sd_test.txt")
    if rc != 0:
        return False
 
    out, err, rc = run_cmd("ls /mnt/sdcard | grep sd_test.txt")
    return rc != 0   # file should NOT exist
 
def unmount_sdcard():
    out, err, rc = run_cmd("umount /mnt/sdcard")
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