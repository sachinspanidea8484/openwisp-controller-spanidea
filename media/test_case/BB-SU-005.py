# START_DESCRIPTION
# 1. Retrieve installed software version from system files.
# 2. Extract VERSION or VERSION_ID field.
# 3. Compare current software version with expected version.
# 4. Verify image integrity by exact version match.
# 5. If version matches expected image, mark test as PASSED.
# END_DESCRIPTION

#!/usr/bin/env python3
import os
import sys
import argparse

from common_helper import (
    log,
    parse_configuration,
    EXIT_SUCCESS,
    EXIT_FAILED
)

VERSION_PATHS = [
    "/etc/os-release",
    "/usr/lib/os-release"
]


def extract_version_from_file(path):
    try:
        with open(path, "r") as f:    # "r" = read mode
            for line in f:
                line = line.strip()     #removes spaces like    " VERSION_ID=\"24.10\" \n" --->  "VERSION_ID=\"24.10\""
                if not line:
                    continue

                # Check if line contains version keywords
                if any(k in line for k in ["VERSION_ID", "VERSION", "version"]):
                    parts = line.split("=", 1)    # ["VERSION_ID", '"24.10-SNAPSHOT"']
                    if len(parts) == 2:
                        return parts[1].strip().strip('"\'')
                    else:
                        return line.strip()
        return None
    except Exception:
        return None

"""to check version """
def get_software_version():
    for path in VERSION_PATHS:
        if os.path.isfile(path):
            log("Found version file: %s", path)
            version = extract_version_from_file(path)
            if version:
                return version
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Software Version Verification Test"
    )
    parser.add_argument(
        "config",
        help="CONFIGURATION='{\"expected_version\":\"24.10-SNAPSHOT\"}'"
    )
    args = parser.parse_args()

    # Parse CONFIGURATION JSON
    config = parse_configuration(args.config)

    expected_version = config.get("expected_version")
    if not expected_version:
        log("Missing 'expected_version' in CONFIGURATION JSON", level="FAIL")
        return EXIT_FAILED

    log("[STEP 1] Starting Software Version Verification Test")

    # Get actual software version from system
    current_version = get_software_version()
    if not current_version:
        log("Unable to retrieve current software version from system", level="FAIL")
        return EXIT_FAILED

    log("Retrieved Software Version: %s", current_version)
    log("Expected Software Version: %s", expected_version)

    # Compare expected vs actual
    if current_version == expected_version:
        log("Software image version matches the expected version", level="PASS")
        log("Test Case PASSED", level="PASS")
        return EXIT_SUCCESS
    else:
        log(
            "Expected version '%s' but found '%s'",
            expected_version,
            current_version,
            level="FAIL"
        )
        log("Test Case FAILED", level="FAIL")
        return EXIT_FAILED


if __name__ == "__main__":
     sys.exit(main())


#  python3 BB-SU-005.py CONFIGURATION='{"expected_version":"23.05.5"}'

