import os
import sys
from datetime import datetime

# === Expected Software Version ===
EXPECTED_VERSION = "23.05.5"

# === Possible version file paths ===
VERSION_PATHS = [
    "/etc/version",
    "/etc/os-release",
    "/usr/lib/os-release"
]

# === Logging Utility ===
def log(message):
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{timestamp} {message}")

# === Function to extract version string from file ===
def extract_version_from_file(path):
    try:
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                # Common fields in os-release or version files
                if any(k in line for k in ["VERSION_ID", "VERSION", "version"]):
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        value = parts[1].strip().strip('"\'')
                        return value
                    else:
                        return line.strip()
        return None
    except Exception as e:
        log(f"[ERROR] Could not read {path}: {e}")
        return None

# === Retrieve current software version ===
def get_software_version():
    for path in VERSION_PATHS:
        if os.path.isfile(path):
            log(f"[INFO] Found version file: {path}")
            version = extract_version_from_file(path)
            if version:
                return version
    return None

# === Main Test ===
def main():
    log("[STEP 1] Starting Software Version Verification Test")

    current_version = get_software_version()

    if not current_version:
        log("[FAIL] Unable to retrieve current software version from system.")
        sys.exit(1)

    log(f"[INFO] Retrieved Software Version: {current_version}")
    log(f"[INFO] Expected Software Version: {EXPECTED_VERSION}")

    if current_version == EXPECTED_VERSION:
        log("[PASS] Software image version matches the expected version.")
        log("[PASS] Test Case PASSED.")
    else:
        log(f"[FAIL] Software version mismatch: Expected '{EXPECTED_VERSION}', Found '{current_version}'")
        log("[FAIL] Test Case FAILED.")
        sys.exit(1)

if __name__ == "__main__":
    main()

