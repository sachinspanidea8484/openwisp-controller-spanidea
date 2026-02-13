import subprocess
import sys
import os
from datetime import datetime

# === Configurable Parameters ===
VOLTAGE_MIN = 0.8
VOLTAGE_MAX = 1.2
CURRENT_MIN = 0.0
CURRENT_MAX = 5.0
NUM_READS = 5
SENSOR_SCRIPT = "/usr/bin/sensor_monitor.py"
TARGET_SENSOR = "INA220_HWMON6"  # Only check this sensor

# === Utility Functions ===
def log(message):
    """Print timestamped log messages."""
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{timestamp} {message}")

def run_local_command(command):
    """Run a local command and capture output."""
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        log(f"[ERROR] Command failed: {' '.join(command)}")
        log(f"[ERROR] STDERR: {e.stderr.strip() if e.stderr else 'N/A'}")
        sys.exit(1)

def verify_file_exists(filepath):
    """Verify that a required file exists."""
    if not os.path.isfile(filepath):
        log(f"[FAIL] Required file not found: {filepath}")
        sys.exit(1)
    log(f"[PASS] Verified file exists: {filepath}")

def extract_target_block(output):                                                   
    """Extract ONLY the block of lines for INA220_HWMON6."""                        
    lines = output.splitlines()                                                     
    block = []                                                                      
    inside_target = False                                                           
                                                                                    
    for line in lines:                                                              
        if TARGET_SENSOR in line:                                                   
            inside_target = True                                                    
            block.append(line)                                                      
            continue                                                                
        if inside_target:                                                           
            if line.strip() == "":  # blank line = end of block                     
                break                                                               
            block.append(line)                                                      
    return "\n".join(block)                                                         
                                                                                    
def parse_sensor_output(block):                                                     
    """Parse INA220_HWMON6 block to extract Bus Voltage and Current."""             
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
    
def validate_reading(voltage, current, iteration):                                                                         
    """Validate a single sensor reading and return (status, message)."""                                                   
    if voltage is None or current is None:                                                                                 
        return False, f"[FAIL] Iteration {iteration}: Could not parse {TARGET_SENSOR} output"                              
                                                                                                                           
    if not (VOLTAGE_MIN <= voltage <= VOLTAGE_MAX):                                                                        
        return False, f"[FAIL] Iteration {iteration}: Voltage {voltage:.2f} V out of range ({VOLTAGE_MIN}-{VOLTAGE_MAX} V)"
                                                                                                                           
    if not (CURRENT_MIN <= current <= CURRENT_MAX):                                                                        
        return False, f"[FAIL] Iteration {iteration}: Current {current:.2f} A out of range ({CURRENT_MIN}-{CURRENT_MAX} A)"
                                                                                                                           
    return True, None 
    
# === Main Test ===                                                                                                        
def main():                                                                                                                
    log("[STEP 1] Starting CPU Input Power Test (BB-DEV-PWR-002)")                                                         
                                                                                                                           
    # Verify that sensor_monitor.py exists                                                                                 
    verify_file_exists(SENSOR_SCRIPT)                                                                                      
                                                                                                                           
    log("[STEP 2] Reading sensor data...\n")                                                                               
    total_passed = True                                                                                                    
    previous_voltage = None                                                                                                
    previous_current = None                                                                                                
    changing_detected = False                                                                                              
    failure_message = None                                                                                                 
                                                                                                                           
    for i in range(1, NUM_READS + 1):                                                                                      
        output = run_local_command([SENSOR_SCRIPT])                                                                        
        if not output:                                                                                                     
            failure_message = f"[FAIL] Iteration {i}: No output received from {SENSOR_SCRIPT}"                             
            total_passed = False                                                                                           
            break                                                                                                          
                                                                                                                           
        block = extract_target_block(output)                                                                               
        voltage, current = parse_sensor_output(block)                                                                      
        print(f"\n[{i}] Retrieved {TARGET_SENSOR} Data:\n{block}")                                                         
                                                                                                                           
        passed, message = validate_reading(voltage, current, i)                                                            
        if not passed:                                                                                                     
            failure_message = message                                                                                      
            total_passed = False                                                                                           
            break                                                                                                          
                                                                                                                           
        # Detect minor variation between reads                                                                             
        if previous_voltage is not None and (                                                                              
            abs(voltage - previous_voltage) > 0.01 or abs(current - previous_current) > 0.01                               
        ):                                                                                                                 
            changing_detected = True                                                                                       
                                                                                                                           
        previous_voltage = voltage                                                            
        previous_current = current                                                           
                                                                                                                           
    # Final results summary                                                                                                
    if total_passed:                                                                                                       
        if not changing_detected:                                                             
            log("[WARN] Sensor readings appear static ... check if data is updating.")       
        log("[PASS] CPU Input Power Test PASSED")                                                                       
    else:                                                                                                                  
        print(failure_message)                                                                                             
        log("[FAIL] CPU Input Power Test FAILED")                                                                          
        sys.exit(1)                                                                                                        
                                                                                                                           
if __name__ == "__main__":                                                                                                 
    main()                      
    
    
    
    
    
    
    
