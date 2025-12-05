from datetime import datetime
import subprocess


def log(msg):
    timestamp = datetime.now().strftime("[%Y%m%d-%H%M%S]")
    print(f"{timestamp} {msg}")

def run_cmd(cmd):
    """Run a shell command and return (stdout, stderr, returncode)."""
    try:
        result = subprocess.Popen(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        out, err = result.communicate(timeout=10)
        return out.strip(), err.strip(), result.returncode
    except Exception as e:
        return "", str(e), 1


def check_sdcard_present():
    """Check if SD card is detected on NXP board (no lsblk)."""
    out, err, rc = run_cmd("ls /dev | grep mmcblk")
    return rc == 0   


def mount_sdcard():
    """Mount SD card to /mnt/sdcard."""
    run_cmd("mkdir -p /mnt/sdcard")
    out, err, rc = run_cmd("mount /dev/mmcblk0p1 /mnt/sdcard")
    return rc == 0


def verify_mount():
    """Verify SD card is mounted."""
    out, err, rc = run_cmd("df -h | grep /mnt/sdcard")
    return rc == 0


def write_test_file():
    """Write test file to SD card."""
    cmd = 'echo "SD Card Automation Test" > /mnt/sdcard/sd_test.txt'
    out, err, rc = run_cmd(cmd)
    return rc == 0


def read_test_file():
    """Read test file and verify content."""
    out, err, rc = run_cmd("cat /mnt/sdcard/sd_test.txt")
    if rc != 0:
        return False
    return "SD Card Automation Test" in out


def delete_test_file():
    """Delete the test file."""
    out, err, rc = run_cmd("rm /mnt/sdcard/sd_test.txt")
    if rc != 0:
        return False

    # confirm deletion
    out, err, rc = run_cmd("ls /mnt/sdcard | grep sd_test.txt")
    return rc != 0  # rc != 0 means file not found → success


def unmount_sdcard():
    """Unmount the SD card."""
    out, err, rc = run_cmd("umount /mnt/sdcard")
    return rc == 0


# ======================
# MAIN TEST ENTRY POINT
# ======================

def run_test():
    log("=== BB-SU-008 : SD Card Slot Verification ===")

    # Step 1: SD card detection
    if not check_sdcard_present():
        log("[FAIL] SD card not detected.")
        return False
    log("[INFO] SD card detected.")

    # Step 2: Mount
    mount_sdcard()
    if not verify_mount():
        log("[FAIL] Unable to mount SD card.")
        return False
    log("[INFO] SD card mounted.")

    # Step 3: Write
    if not write_test_file():
        log("[FAIL] Failed to write test file.")
        return False
    log("[INFO] Write successful.")

    # Step 4: Read
    if not read_test_file():
        log("[FAIL] Failed to read/verify test file.")
        return False
    log("[INFO] Read successful.")

    # Step 5: Delete
    if not delete_test_file():
        log("[FAIL] Failed to delete test file.")
        return False
    log("[INFO] Delete successful.")

    # Step 6: Unmount
    unmount_sdcard()
    log("[INFO] SD card unmounted.")

    log("[PASS]Testcase Passed successfully")
    return True


if __name__ == "__main__":
    run_test()

