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


def induce_kernel_event():
    log("Inducing kernel event (MTU change)...")

    run_local_command("ifconfig eth0 mtu 1", check=False, allow_fail=True)

    stdout, _, _ = run_local_command("dmesg | tail -n 5")

    if "eth0" not in stdout:
        raise AssertionError("MTU change error not logged in dmesg")

    log("MTU change error logged in dmesg.", level="PASS")


def main():
    log("=== Starting Logging Testcase ===")

    try:
        verify_logread()
        generate_user_logs()
        check_dmesg()
        generate_system_log()
        generate_kernel_log()
        check_logd()
        induce_kernel_event()

    except AssertionError as ae:
        log("Assertion Failed: %s", ae, level="FAIL")
        sys.exit(EXIT_FAILED)

    except Exception as e:
        log("Unexpected Error: %s", e, level="FAIL")
        sys.exit(EXIT_FAILED)

    log("All logging tests passed successfully.", level="PASS")
    sys.exit(EXIT_SUCCESS)


if __name__ == "__main__":
    main()
