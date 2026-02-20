import subprocess
import time
import re
import sys
import os

# Configurable number of readings
READING_COUNT = 5

def run_command(command):
    """
    Runs a shell command locally and returns stdout, stderr.
    """
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.stdout.strip(), result.stderr.strip()

def extract_hwmon8_section(output):
    """
    Extract only the SA56004_HWMON8 block from the sensor output.
    """
    match = re.search(r"(SA56004_HWMON8.*?)(?=\n\S|$)", output, re.DOTALL)
    return match.group(1).strip() if match else None

def parse_and_format(section):
    """
    Parses the SA56004_HWMON8 block and returns dictionary + formatted string.
    """
    # Look for "I..C Bus" and "I..C Address" literally
    i2c_bus_match = re.search(r"I..C\s+Bus\s*:\s*(\S+)", section)
    i2c_addr_match = re.search(r"I..C\s+Address\s*:\s*(\S+)", section)
    local_temp_match = re.search(r"Local\s+Temp.*?:\s*([\d\.]+)", section)
    remote_temp_match = re.search(r"Remote\s+Temp.*?:\s*([\d\.]+)", section)

    i2c_bus = i2c_bus_match.group(1) if i2c_bus_match else "N/A"
    i2c_addr = i2c_addr_match.group(1) if i2c_addr_match else "N/A"
    local_temp = float(local_temp_match.group(1)) if local_temp_match else None
    remote_temp = float(remote_temp_match.group(1)) if remote_temp_match else None

    formatted = (
        f"  I..C Bus               : {i2c_bus}\n"
        f"  I..C Address           : {i2c_addr}\n"
        f"  Local Temp (..C)       : {local_temp if local_temp is not None else 'N/A'}\n"
        f"  Remote Temp (..C)      : {remote_temp if remote_temp is not None else 'N/A'}\n"
    )

    return {"local": local_temp, "remote": remote_temp}, formatted

def verify_cpu_temperature():                                                              
    sensor_script = "/usr/bin/sensor_monitor.py"                                           
                                                                                           
    # STEP 0: Check script presence                                                        
    if not os.path.exists(sensor_script):                                                  
        print(f"[ERROR] Sensor script not found at {sensor_script}")                       
        print("[RESULT] FAILURE ... Missing sensor script.")                               
        sys.exit(1)                                                                        
                                                                                           
    print("[STEP 1] Fetching only SA56004_HWMON8 readings locally...\n")                   
                                                                                           
    readings = []  # Store tuples of (local, remote)                                       
                                                                                           
    for i in range(READING_COUNT):                                                         
        output, error = run_command(f"python3 {sensor_script}")                            
                                                                                           
        if error:                                                                          
            print(f"[{i+1}] [ERROR] Sensor command STDERR: {error}\n")                     
            print("[RESULT] FAILURE ... Device Temperature test failed.")                  
            sys.exit(1)                                                                    
                                                                                           
        section = extract_hwmon8_section(output)                                           
        if section:                                                                        
            temps, formatted = parse_and_format(section)                                   
            print(f"[{i+1}] SA56004_HWMON8")                                               
            print(formatted)                                                               
                                                                                           
            if temps["local"] is not None and temps["remote"] is not None:                 
                readings.append((temps["local"], temps["remote"]))                         
                # Range check                                                              
                if not (-45 <= temps["local"] <= 80):                                      
                    print(f"[{i+1}] [ERROR] Local temperature {temps['local']}..C out of range (-45 to 80).")
                    print("[RESULT] FAILURE ... Device Temperature test failed")                             
                    sys.exit(1)                                                                              
                if not (-45 <= temps["remote"] <= 80):                                                       
                    print(f"[{i+1}] [ERROR] Remote temperature {temps['remote']}..C out of range (-45 to 80).")
                    print("[RESULT] FAILURE ... Device Temperature test failed")                               
                    sys.exit(1)                                                                                
            else:                                                                                              
                print(f"[{i+1}] [ERROR] Could not parse temperatures.\n")                                      
                print("[RESULT] FAILURE ... Device Temperature test failed")                                   
                sys.exit(1)                                                                                    
        else:                                                                                                  
            print(f"[{i+1}] [ERROR] SA56004_HWMON8 section not found.\n")                                      
            print("[RESULT] FAILURE ... Device Temperature test failed")                                       
            sys.exit(1)                                                                                        
                                                                                                               
        time.sleep(1)                                                                                          
                                                                                                               
    # STEP 2: Identical values check (only if we collected all valid readings)                                 
    if len(readings) == READING_COUNT:                                                                         
        if all(r == readings[0] for r in readings):                                                            
            print("[ERROR] All readings are identical. Possible hard-coded values, not live sensor data.")     
            print("[RESULT] FAILURE ... Device Temperature test failed")                                       
            sys.exit(1)                                                                                        
                                                                                                               
    # Final test result                                                                                        
    print("[RESULT] SUCCESS ... All SA56004_HWMON8 checks passed.")                                            
    sys.exit(0)                                                                                                
                                                                                                               
if __name__ == "__main__":                                                                                     
    verify_cpu_temperature()                               
        
        
        
        
        
