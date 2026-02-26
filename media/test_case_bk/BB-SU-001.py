# START_DESCRIPTION
# 1. Start CDM-BB Startup LED verification test.
# 2. Read GPIO states for Green, Red, and Blue LEDs using gpioget.
# 3. Repeat GPIO sampling for configured number of iterations.
# 4. Verify expected startup condition:
#        a. Green LED = ON (GPIO value 0)
#        b. Red LED   = OFF (GPIO value 1)
#        c. Blue LED  = OFF (GPIO value 1)
# 5. If any mismatch occurs during iterations, mark test as FAILED.
# 6. If all samples match expected LED behavior, mark test as PASSED.
# END_DESCRIPTION

import sys
import os
import time

# Import Common Helper
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Common')))
from common_helper import (
    log,
    run_local_command,
    EXIT_SUCCESS,
    EXIT_FAILED
)

# === Configurable Parameters ===
CHIP = "8"                # GPIO chip
PIN_GREEN = "10"          # Solid Green LED pin
PIN_RED = "9"             # Red LED pin
PIN_BLUE = "11"           # Blue LED pin
ITERATIONS = 100          # Number of samples
SLEEP_DURATION = 0.1      # Delay between iterations (in seconds)


# === GPIO Reader ===
def get_gpio_state(chip, line):
    """
    Reads GPIO state using gpioget.
    Returns '0' or '1' if successful, otherwise None.
    """
    command = f"gpioget gpiochip{chip} {line}"
    stdout, stderr, rc = run_local_command(command, allow_fail=True)

    if rc != 0 or stderr:
        log("Failed to read GPIO gpiochip%s line %s", chip, line, level="FAIL")
        return None

    return stdout.strip()


# === Main Verification Logic ===
def main():
    log("=== CDM-BB Startup LED Verification Started ===")
    log("Verifying Solid Green LED startup sequence (%d samples)...", ITERATIONS)

    success = True

    for i in range(1, ITERATIONS + 1):

        green = get_gpio_state(CHIP, PIN_GREEN)
        red   = get_gpio_state(CHIP, PIN_RED)
        blue  = get_gpio_state(CHIP, PIN_BLUE)

        if green is None or red is None or blue is None:
            log("Iteration %d: Failed to read GPIO values.", i, level="FAIL")
            success = False
            break

        log("Iteration %d: Green=%s, Red=%s, Blue=%s",
            i, green, red, blue)

        # Expected condition:
        # Green = 0 (ON)
        # Red   = 1 (OFF)
        # Blue  = 1 (OFF)
        if not (green == "0" and red == "1" and blue == "1"):
            log("Mismatch at iteration %d/%d | Expected G=0 R=1 B=1 | Got G=%s R=%s B=%s",
                i, ITERATIONS, green, red, blue, level="FAIL")
            success = False
            break

        time.sleep(SLEEP_DURATION)

    if success:
        log("CDM-BB startup verified: Solid Green ON, Red & Blue OFF (%d/%d checks).",
            ITERATIONS, ITERATIONS, level="PASS")
        sys.exit(EXIT_SUCCESS)
    else:
        log("CDM-BB startup verification failed.", level="FAIL")
        sys.exit(EXIT_FAILED)


if __name__ == "__main__":
    main()

