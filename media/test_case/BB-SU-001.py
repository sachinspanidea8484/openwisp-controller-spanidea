"""
CDM-BB Solid Green LED Startup Verification using common_helper.py
"""

from common_helper import log, run_local_command
import time
import sys

# === Configurable Parameters ===
CHIP = "8"  
PIN_RED = "9"                           
PIN_GREEN = "10"          
PIN_BLUE = "11"           
ITERATIONS = 100          
SLEEP_DURATION = 0.1      

def get_gpio_state(chip, line):
    """
    Reads the GPIO state (returns value as string '0' or '1').
    """
    command = f"gpioget gpiochip{chip} {line}"
    stdout, stderr = run_local_command(command, allow_fail=True)
    if stderr:
        return None
    return stdout

def main():                        
    log(f"STEP 1: Verifying GPIO states for Solid Green LED ({ITERATIONS} samples)...")
                               
    success = True
                                                                                    
    for i in range(1, ITERATIONS + 1):  
        red   = get_gpio_state(CHIP, PIN_RED)
        green = get_gpio_state(CHIP, PIN_GREEN)
        blue  = get_gpio_state(CHIP, PIN_BLUE)
                               
        if green is None or red is None or blue is None:
            log("ITER %d: ERROR - Failed to read GPIO values.", i)
            success = False
            break                             
                                               
        log("ITER %d: Green=%s, Red=%s, Blue=%s", i, green, red, blue)
                   
        if not (green == "0" and red == "1" and blue == "1"):
            log("FAIL: Condition mismatch at iter %d. Expected: G0 R1 B1 | Got: G%s R%s B%s", 
                 i, green, red, blue, level="FAIL")
            success = False
            break                                                                                         

        time.sleep(SLEEP_DURATION)

    if success:                                                   
        log("PASS: CDM-BB startup verified (%d/%d checks).", i - 1, ITERATIONS)  # need to verify
        return EXIT_SUCCESS           
    else:
        log("FAIL: CDM-BB startup verification failed.", level="FAIL")
        return EXIT_FAILED
                           
if __name__ == "__main__":
    main()

