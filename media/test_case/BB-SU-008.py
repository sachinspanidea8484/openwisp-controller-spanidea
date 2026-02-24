# START_DESCRIPTION
# 1. Detect SD card device presence under /dev/mmcblk*.
# 2. Create mount point directory if not existing.
# 3. Mount SD card partition to /mnt/sdcard.
# 4. Verify mount operation using mount command.
# 5. Create a test file on SD card.
# 6. Read the test file and validate written content.
# 7. Delete the test file and confirm removal.
# 8. Unmount SD card cleanly.
# 9. If all steps succeed, mark test as PASSED.
# END_DESCRIPTION

import sys
import os

# Import Common Helper
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Common')))
from common_helper import (
    log,
    run_local_command,
    EXIT_SUCCESS,
    EXIT_FAILED
)

SD_DEVICE = "/dev/mmcblk0p1"
MOUNT_POINT = "/mnt/sdcard"
TEST_FILE = f"{MOUNT_POINT}/sd_test.txt"


# ======================
# SD CARD OPERATIONS
# ======================

def check_sdcard_present():
    stdout, _, rc = run_local_command("ls /dev/mmcblk* 2>/dev/null", allow_fail=True)
    return rc == 0 and stdout != ""


def mount_sdcard():
    run_local_command(f"mkdir -p {MOUNT_POINT}")
    _, _, rc = run_local_command(f"mount {SD_DEVICE} {MOUNT_POINT}", allow_fail=True)
    return rc == 0


def verify_mount():
    stdout, _, rc = run_local_command(f"mount | grep {MOUNT_POINT}", allow_fail=True)
    return rc == 0 and stdout != ""


def write_test_file():
    _, _, rc = run_local_command(
        f'echo "SD Card Automation Test" > {TEST_FILE}',
        allow_fail=True
    )
    return rc == 0


def read_test_file():
    stdout, _, rc = run_local_command(f"cat {TEST_FILE}", allow_fail=True)
    return rc == 0 and "SD Card Automation Test" in stdout


def delete_test_file():
    _, _, rc = run_local_command(f"rm -f {TEST_FILE}", allow_fail=True)
    if rc != 0:
        return False

    stdout, _, rc = run_local_command(
        f"ls {MOUNT_POINT} | grep sd_test.txt",
        allow_fail=True
    )

    return rc != 0  # File should NOT exist


def unmount_sdcard():
    _, _, rc = run_local_command(f"umount {MOUNT_POINT}", allow_fail=True)
    return rc == 0


# ======================
# MAIN TEST ENTRY POINT
# ======================

def run_test():
    log("=== BB-SU-008 : SD Card Slot Verification ===")

    # Step 1: Detect SD Card
    if not check_sdcard_present():
        log("SD card not detected.", level="FAIL")
        return EXIT_FAILED
    log("SD card detected.", level="PASS")

    # Step 2: Mount
    if not mount_sdcard():
        log("SD card mount failed.", level="FAIL")
        return EXIT_FAILED

    if not verify_mount():
        log("SD card not mounted.", level="FAIL")
        return EXIT_FAILED
    log("SD card mounted successfully.", level="PASS")

    # Step 3: Write
    if not write_test_file():
        log("Failed to write test file.", level="FAIL")
        return EXIT_FAILED
    log("Write operation successful.", level="PASS")

    # Step 4: Read
    if not read_test_file():
        log("Failed to read or verify test file.", level="FAIL")
        return EXIT_FAILED
    log("Read operation successful.", level="PASS")

    # Step 5: Delete
    if not delete_test_file():
        log("Failed to delete test file.", level="FAIL")
        return EXIT_FAILED
    log("Delete operation successful.", level="PASS")

    # Step 6: Unmount
    if not unmount_sdcard():
        log("Failed to unmount SD card.", level="FAIL")
        return EXIT_FAILED
    log("SD card unmounted successfully.", level="PASS")

    log("BB-SU-008 Testcase Passed successfully.", level="PASS")
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(run_test())
