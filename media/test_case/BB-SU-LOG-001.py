# START_DESCRIPTION
# 1. Parse CONFIGURATION input and extract the network interface parameter.
# 2. Validate the provided interface exists on the device.
# 3. Restart the system log service to ensure logging is active.
# 4. Verify system logs are accessible using the logread command.
# 5. Generate user-level log messages (debug, info, warning, error) using logger.
# 6. Verify generated user log messages are captured in system logs.
# 7. Check availability of kernel logs using the dmesg command.
# 8. Generate a system log message and verify it appears in logread output.
# 9. Generate a kernel log message using /dev/kmsg and verify it appears in dmesg.
# 10. Verify that the logd process is running.
# 11. Induce a kernel-level network event (MTU change) on the provided interface.
# 12. Verify the MTU change event is logged in dmesg output.
# 13. If all logging mechanisms function correctly, mark the test as PASSED.
# END_DESCRIPTION

#!/usr/bin/env python3
import sys
import os

# Import Common Helper
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Common')))
from common_helper import (
    log,
    run_local_command,
    parse_configuration,
    EXIT_SUCCESS,
    EXIT_FAILED
)


def verify_logread():
    log("Restarting log service...")
    run_local_command("/etc/init.d/log restart")

    stdout, _, _ = run_local_command("logread | head -n 5")
    if not stdout:
        raise AssertionError("System logs not found!")
    log("System logs found.", level="PASS")


def generate_user_logs():
    log("Generating user level logs...")
    levels = [
        ("user.debug", "Test debug message"),
        ("user.info", "Test info message"),
        ("user.warning", "Test warning message"),
        ("user.err", "Test error message"),
    ]

    for level, msg in levels:
        run_local_command(f'logger -p {level} "{msg}"')

    stdout, _, _ = run_local_command("logread | tail -n 10")
    if "Test" not in stdout:
        raise AssertionError("Log messages not captured!")

    log("User-level logs captured.", level="PASS")


def check_dmesg():
    log("Checking kernel logs (dmesg)...")
    stdout, _, _ = run_local_command("dmesg | head -n 5")
    if not stdout:
        raise AssertionError("dmesg output missing")

    log("Kernel logs available.", level="PASS")


def generate_system_log():
    log("Generating system log message...")
    run_local_command('logger "Test system log from user"')

    stdout, _, _ = run_local_command('logread | grep "Test system log"')
    if "Test system log" not in stdout:
        raise AssertionError("System log not found!")

    log("System log message verified.", level="PASS")


def generate_kernel_log():
    log("Generating kernel log message...")
    run_local_command('echo "klog test" > /dev/kmsg')

    stdout, _, _ = run_local_command("dmesg | tail -n 5")
    if "klog test" not in stdout:
        raise AssertionError("Kernel log not found!")

    log("Kernel log message verified.", level="PASS")


def check_logd():
    log("Checking logd process...")
    stdout, _, _ = run_local_command("ps | grep [l]ogd")

    if "logd" not in stdout:
        raise AssertionError("logd not running")

    log("logd process is running.", level="PASS")


def validate_interface(interface):
    log(f"Validating interface: {interface}")
    stdout, _, _ = run_local_command(f"ifconfig {interface}", allow_fail=True)

    if not stdout:
        raise AssertionError(f"Interface {interface} not found!")

    log(f"Interface {interface} is valid.", level="PASS")


def induce_kernel_event(interface):
    log(f"Inducing kernel event (MTU change) on {interface}...")

    run_local_command(f"ifconfig {interface} mtu 1", check=False, allow_fail=True)

    stdout, _, _ = run_local_command("dmesg | tail -n 5")

    if interface not in stdout:
        raise AssertionError(f"MTU change error not logged for {interface}")

    log("MTU change error logged in dmesg.", level="PASS")


def main():
    log("=== LOGGING TEST STARTED ===")

    # ✅ Parse CLI CONFIGURATION
    config = parse_configuration(sys.argv[1] if len(sys.argv) > 1 else None)

    interface = config.get("interface")

    # ✅ Validation
    if not interface:
        log("[FAIL] Missing 'interface' in CONFIGURATION", level="FAIL")
        sys.exit(EXIT_FAILED)

    log(f"[INFO] Using interface: {interface}")

    try:
        validate_interface(interface)
        verify_logread()
        generate_user_logs()
        check_dmesg()
        generate_system_log()
        generate_kernel_log()
        check_logd()
        induce_kernel_event(interface)

    except AssertionError as ae:
        log("Assertion Failed: %s", ae, level="FAIL")
        sys.exit(EXIT_FAILED)

    except Exception as e:
        log("Unexpected Error: %s", e, level="FAIL")
        sys.exit(EXIT_FAILED)

    log("=== ALL LOGGING TESTS PASSED ===", level="PASS")
    sys.exit(EXIT_SUCCESS)


if __name__ == "__main__":
    main()
