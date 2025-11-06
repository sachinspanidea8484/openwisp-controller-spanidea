import os
import sys
import subprocess
from datetime import datetime

# === Expected Counts ===
EXPECTED_MODEMS = 2        
EXPECTED_WIFI = 1

# === Logging Utility ===
def log(message):
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{timestamp} {message}")

# === Detect Installed Modems ===
def get_installed_modems():
    """Detect installed modems using lsusb."""
    modems_found = []

    lsusb_exists = os.path.isfile("/usr/bin/lsusb") or any(
        os.path.exists(path) for path in ["/bin/lsusb", "/sbin/lsusb", "/usr/sbin/lsusb"]
    )

    # === If command is not available, skip detection gracefully ===
    if not lsusb_exists:
        log("[WARN] lsusb is not available. Skipping USB modem detection.")
        return []

    # === lsusb detection ===
    try:
        lsusb_output = subprocess.check_output(["lsusb"], text=True, stderr=subprocess.DEVNULL)
        for line in lsusb_output.splitlines():
            if any(k in line.lower() for k in ["telit", "quectel", "fibocom", "sierra", "huawei", "simcom"]):
                model = line.split(":")[-1].strip()
                modems_found.append(model)
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    return modems_found

# === Detect Wi-Fi Interfaces using iwinfo ===
def get_wifi_interfaces():
    """Detect Wi-Fi interfaces using 'iwinfo | grep Hardware'."""
    wifi_list = []
    try:
        result = subprocess.check_output("iwinfo | grep Hardware", shell=True, text=True, stderr=subprocess.DEVNULL)
        for line in result.splitlines():
            # Example: wlan0     Hardware: 14C3:7603  MediaTek MT7603E 802.11bgn
            iface = line.split()[0].strip()
            if iface not in wifi_list:
                wifi_list.append(iface)
    except subprocess.CalledProcessError:
        pass

    return wifi_list

# === Main Test ===
def main():
    log("[STEP 1] Starting Modem and Wi-Fi Interface Verification Test")

    # Detect hardware
    modems_found = get_installed_modems()
    wifi_found = get_wifi_interfaces()

    modem_count = len(modems_found)
    wifi_count = len(wifi_found)

    log(f"[INFO] Detected Modems ({modem_count}): {modems_found or 'None'}")
    log(f"[INFO] Detected Wi-Fi Interfaces ({wifi_count}): {wifi_found or 'None'}")

    test_passed = True

    # === Verify Modem Count ===
    if modem_count == EXPECTED_MODEMS:
        log(f"[PASS] Expected {EXPECTED_MODEMS} modem(s), found {modem_count}.")
    else:
        log(f"[FAIL] Expected {EXPECTED_MODEMS} modem(s), found {modem_count}.")
        test_passed = False

    # === Verify Wi-Fi Interface Count ===
    if wifi_count == EXPECTED_WIFI:
        log(f"[PASS] Expected {EXPECTED_WIFI} Wi-Fi interface(s), found {wifi_count}.")
    else:
        log(f"[FAIL] Expected {EXPECTED_WIFI} Wi-Fi interface(s), found {wifi_count}.")
        test_passed = False

    # === Final Result ===
    if test_passed:
        log("[PASS] All expected modem and Wi-Fi interface counts verified successfully.")
        log("[PASS] Test Case PASSED.")
    else:
        log("[FAIL] Test Case FAILED.")
        sys.exit(1)

if __name__ == "__main__":
    main()

