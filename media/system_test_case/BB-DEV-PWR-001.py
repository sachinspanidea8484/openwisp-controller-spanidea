import subprocess
import sys
import os
from datetime import datetime

# === Configurable Parameters ===
EXPECTED_VOLTAGE = 12.0
VOLTAGE_TOLERANCE = 2.0
CURRENT_MIN = 0.0
CURRENT_MAX = 5.0
NUM_READS = 5
SENSOR_SCRIPT = "/usr/bin/sensor_monitor.py"
TARGET_SENSOR = "INA220_HWMON7"

# === Utility Functions ===
def log(message):
    """Print timestamped log message."""
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{timestamp} {message}")

def run_local_command(command):
    """Run a local command and capture its output."""
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        log(f"[ERROR] Command failed: {' '.join(command)}")
        log(f"[ERROR] STDERR: {e.stderr.strip() if e.stderr else 'N/A'}")
        sys.exit(1)

def verify_file_exists(filepath):
    """Ensure the sensor script file exists."""
    if not os.path.isfile(filepath):
        log(f"[FAIL] Required file not found: {filepath}")
        sys.exit(1)
    log(f"[PASS] Verified file exists: {filepath}")

def extract_target_block(output):                                                   
    """Extract ONLY the block of lines for the target sensor."""                    
    lines = output.splitlines()                                                     
    block = []                                                                      
    inside_target = False                                                           
                                                                                    
    for line in lines:                                                              
        if TARGET_SENSOR in line:                                                   
            inside_target = True                                                    
            block.append(line)                                                      
            continue                                                                
        if inside_target:                                                           
            if line.strip() == "":                                                  
                break                                                               
            block.append(line)                                                      
    return "\n".join(block)                                                         
                                                                                    
def parse_sensor_output(block):                                                     
    """Parse sensor output to extract Bus Voltage and Current."""                   
    voltage = None                                                                  
    current = None                                                                  
    for line in block.splitlines():                                                 
        if "Bus Voltage" in line:                                                   
            try:                                                                    
                voltage = float(line.split(":")[1].strip())              
            except Exception:                                            
                pass                                                     
        elif "Current (A)" in line:                                      
            try:                                                 
                current = float(line.split(":")[1].strip())      
            except Exception:                                    
                pass                                             
    return voltage, current         

# === Main Test ===                                                                 
def main():                                                                         
    log("[STEP 1] Starting Input Power Verification Test")                          
                                                                                    
    # Verify the sensor script exists                                               
    verify_file_exists(SENSOR_SCRIPT)                                               
                                                                                    
    log("[STEP 2] Retrieving input power data...\n")                                
    previous_voltage = None                                                         
    previous_current = None                                                         
    changing_detected = False                                                       
    total_passed = True  # Track overall success                                    
                                                                                    
    voltage_min = EXPECTED_VOLTAGE - VOLTAGE_TOLERANCE                              
    voltage_max = EXPECTED_VOLTAGE + VOLTAGE_TOLERANCE                              
                                                                                    
    for i in range(1, NUM_READS + 1):                                               
        output = run_local_command([SENSOR_SCRIPT])                                 
        if not output:                                                              
            log(f"[FAIL] No output received from {SENSOR_SCRIPT}")                  
            total_passed = False                                                    
            break                                                                   
                                                                                    
        block = extract_target_block(output)                                        
        voltage, current = parse_sensor_output(block)                    
                                                                         
        print(f"\n[{i}] Retrieved {TARGET_SENSOR} Data:\n{block}")       
                                                                         
        # --- Voltage Validation ---                              
        if voltage is None:                                       
            log(f"[FAIL] Iteration {i}: Could not parse voltage from sensor output")
            total_passed = False                                                    
            break                                                                   
                                                                                    
        if not (voltage_min <= voltage <= voltage_max):                             
            log(f"[FAIL] Iteration {i}: Voltage {voltage:.2f} V out of range ({voltage_min}-{voltage_max} V)")
            total_passed = False                                                                              
            break                                                                                             
                                                                                                              
        # --- Optional Current Check (not shown in fail message) ---                                          
        if current is None or not (CURRENT_MIN <= current <= CURRENT_MAX):                                    
            log(f"[FAIL] Iteration {i}: Current {current:.2f} A out of range ({CURRENT_MIN}-{CURRENT_MAX} A)")
            total_passed = False                                                                              
            break                                                                                             
                                                                                                              
        # Detect changing values                                                                              
        if previous_voltage is not None and (                                                                 
            abs(voltage - previous_voltage) > 0.01 or abs(current - previous_current) > 0.01                  
        ):                                                                                                    
            changing_detected = True                                                                          
                                                                                                              
        previous_voltage = voltage                                                                            
        previous_current = current                                                                            
                                                                                                              
    # === Final Result Summary ===                                                                            
    if total_passed:                                                                                          
        if not changing_detected:                                                                             
            log("[WARN] Sensor readings appear static ... verify live data source.")                          
        log("[PASS] Input Power Verification: All readings within expected range.")                           
                                                                                                              
    if not total_passed:                                                                                      
        sys.exit(1)                                                                                           
                                                                                                              
if __name__ == "__main__":                                                                                    
    main()                               
