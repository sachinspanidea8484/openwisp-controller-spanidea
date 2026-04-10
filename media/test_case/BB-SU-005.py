# START_DESCRIPTION
# 1. Accept the expected software version from CONFIGURATION input.
# 2. Validate that 'expected_version' is provided in the configuration JSON.
# 3. Search for OS version files in standard paths:
#    - /etc/os-release
#    - /usr/lib/os-release
# 4. If a version file is found, read its contents line by line.
# 5. Extract the software version from fields like VERSION_ID, VERSION, or version.
# 6. If no version information is found, mark the test as FAILED.
# 7. Log the retrieved software version.
# 8. Compare the retrieved version with the expected version using regex matching.
# 9. If the expected version pattern is found in the current version, mark the test as PASSED.
# 10. If the expected version pattern is not found, mark the test as FAILED.
# 11. Exit with success or failure status accordingly.
# END_DESCRIPTION

#!/usr/bin/env python3
import os
import sys
import argparse
import re

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
        with open(path, "r") as f:
            for line in f:
                line = line.strip()

                if not line:
                    continue

                # Look for version fields
                if any(k in line for k in ["VERSION_ID", "VERSION", "version"]):
                    parts = line.split("=", 1)

                    if len(parts) == 2:
                        return parts[1].strip().strip('"\'')
                    else:
                        return line.strip()

        return None

    except Exception:
        return None


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
        description="Software Version Verification Test (Regex Based)"
    )
    parser.add_argument(
        "config",
        help="CONFIGURATION='{\"expected_version\":\"24.10-SNAPSHOT\"}'"
    )
    args = parser.parse_args()

    config = parse_configuration(args.config)

    expected_version = config.get("expected_version")

    if not expected_version:
        log("Missing 'expected_version' in CONFIGURATION JSON", level="FAIL")
        sys.exit(EXIT_FAILED)

    log("=== SOFTWARE VERSION VERIFICATION STARTED ===")

    # Get current version
    current_version = get_software_version()

    if not current_version:
        log("Unable to retrieve current software version", level="FAIL")
        sys.exit(EXIT_FAILED)

    log("Retrieved Software Version: %s", current_version)
    log("Expected Version Pattern: %s", expected_version)

    # ---------------- REGEX MATCH ----------------
    pattern = re.escape(expected_version)

    if re.search(pattern, current_version):
        log(
            "Version Match SUCCESS → Pattern '%s' found in '%s'",
            expected_version,
            current_version,
            level="PASS"
        )

        log("NOTE: Full image may include build/date metadata", level="INFO")
        log("Test Case PASSED", level="PASS")
        sys.exit(EXIT_SUCCESS)

    else:
        log(
            "Version Match FAILED → Pattern '%s' NOT found in '%s'",
            expected_version,
            current_version,
            level="FAIL"
        )

        log("Test Case FAILED", level="FAIL")
        sys.exit(EXIT_FAILED)


if __name__ == "__main__":
    main()
