import subprocess
import sys
from datetime import datetime


def log(message):
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{timestamp} {message}")

def run_local_command(command):
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return "", str(e)

def verify_gpio_state(chip, line, expected_state, led_name):
    command = f"gpioget gpiochip{chip} {line}"
    log(f"[INFO] Checking GPIO for {led_name} via command: {command}")
    stdout, stderr = run_local_command(command)

    if stderr:
        log(f"[ERROR] Command failed: {stderr}")
        return False

    if stdout == expected_state:
        log(f"[PASS] {led_name} state is correct ('{expected_state}').")
        return True
    else:
        log(f"[FAIL] {led_name} state is NOT '{expected_state}'. Actual: '{stdout}'")
        return False

def main():
    log("[STEP 1] Verifying GPIO for Solid Green LED (Startup Completion)...")

    # Ensure only line 10 is ON (0), and 9 and 11 are OFF (1)
    green_ok = verify_gpio_state("8", "10", "0", "Solid Green Power LED")
    red_off = verify_gpio_state("8", "9", "1", "Panel4 Red LED (should be OFF)")
    blue_off = verify_gpio_state("8", "11", "1", "Panel4 Blue LED (should be OFF)")

    if green_ok and red_off and blue_off:
        log("[PASS] CDM-BB has successfully completed startup (Solid Green only).")
        sys.exit(0)  
    else:
        log("[FAIL] CDM-BB startup sequence failed or still in progress.")
        sys.exit(1) 

if __name__ == "__main__":
    main()

