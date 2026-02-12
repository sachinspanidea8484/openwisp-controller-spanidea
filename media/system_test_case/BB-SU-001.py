import subprocess
import sys
import time
from datetime import datetime

# === Configurable Parameters ===
CHIP = "8"                # GPIO chip
PIN_GREEN = "10"          # Solid Green LED pin
PIN_RED = "9"             # Red LED pin
PIN_BLUE = "11"           # Blue LED pin
ITERATIONS = 100          # Number of samples
SLEEP_DURATION = 0.1      # Delay between iterations (in seconds)

# === Utility Functions ===
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

# === Main Verification Logic ===                             
def main():                        
    log(f"[STEP 1] Verifying GPIO states for Solid Green LED startup sequence ({ITERATIONS} samples)...")
                               
    success = True
                                                                                    
    for i in range(1, ITERATIONS + 1):  # Loop based on ITERATIONS
        green = get_gpio_state(CHIP, PIN_GREEN)
        red   = get_gpio_state(CHIP, PIN_RED)
        blue  = get_gpio_state(CHIP, PIN_BLUE)
                               
        if green is None or red is None or blue is None:
            log(f"[ITER {i}] [ERROR] Failed to read GPIO values.")
            success = False
            break                             
                                               
        log(f"[ITER {i}] Green={green}, Red={red}, Blue={blue}")
                   
        if not (green == "0" and red == "1" and blue == "1"):
            log(f"[FAIL] Condition mismatch at iteration {i}/{ITERATIONS}. "
                f"Expected: Green=0, Red=1, Blue=1 | Got: Green={green}, Red={red}, Blue={blue}")
            success = False
            break                                                                                        

        time.sleep(SLEEP_DURATION)

    if success:                                                   
        log(f"[PASS] CDM-BB startup verified: Solid Green LED always ON, "
            f"Red & Blue always OFF ({ITERATIONS}/{ITERATIONS} checks).")
        sys.exit(0)                           
    else:
        log("[FAIL] CDM-BB startup verification failed.")
        sys.exit(1)                                               
                           
if __name__ == "__main__":
    main()

