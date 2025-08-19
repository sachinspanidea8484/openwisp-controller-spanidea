import subprocess
import sys
import time
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

def get_gpio_state(chip, line):
    """
    Reads the GPIO state (returns value as string '0' or '1').
    """
    command = f"gpioget gpiochip{chip} {line}"
    stdout, stderr = run_local_command(command)
    if stderr:
        return None
    return stdout

def main():
    log("[STEP 1] Verifying GPIO states for Solid Green LED startup sequence (100 samples)...")

    chip = "8"
    success = True

    for i in range(1, 101):  # 100 iterations
        green = get_gpio_state(chip, "10")  # Solid Green
        red   = get_gpio_state(chip, "9")   # Red
        blue  = get_gpio_state(chip, "11")  # Blue

        if green is None or red is None or blue is None:
            log(f"[ITER {i}] [ERROR] Failed to read GPIO values.")
            success = False
            break

        log(f"[ITER {i}] Green={green}, Red={red}, Blue={blue}")

        if not (green == "0" and red == "1" and blue == "1"):
            log(f"[FAIL] Condition mismatch at iteration {i}/100. "
                f"Expected: Green=0, Red=1, Blue=1 | Got: Green={green}, Red={red}, Blue={blue}")
            success = False
            break

        time.sleep(0.1)  # 100 ms delay

    if success:
        log("[PASS] CDM-BB startup verified: Solid Green LED always ON, Red & Blue always OFF (100/100 checks).")
        sys.exit(0)
    else:
        log("[FAIL] CDM-BB startup verification failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()

