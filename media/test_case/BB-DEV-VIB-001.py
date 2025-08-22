import subprocess                                            
import sys                                                                             
import os                                                                              
from datetime import datetime                                   
                                                                                    
SENSOR_SCRIPT = "/usr/bin/read_sensor.py"                                        
NUM_READS = 5                                                        
                                                                           
def log(message):                                                           
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{timestamp} {message}")                       
                                                                
def run_local_command(command):                                                      
    try:                                                                             
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return result.stdout.strip(), result.stderr.strip()                
    except Exception as e:                                                             
        return "", str(e)                                
                                           
def parse_sensor_data(output):                                                   
    lines = output.strip().splitlines()                              
    gyro_data = {}                                                           
    accel_data = {}                                                                    
                                                      
    for line in lines:                                                       
        if line.startswith("Gyro:"):                                             
            gyro_str = line.replace("Gyro:", "").strip()
            gyro_data = eval(gyro_str)                                               
        elif line.startswith("Accel:"):                        
            accel_str = line.replace("Accel:", "").strip()           
            accel_data = eval(accel_str)                                               
                                                                            
    if not gyro_data or not accel_data:
        raise ValueError("Missing Gyro or Accel data")                               
                                                                           
    return gyro_data, accel_data

def verify_vibration_data():                                                     
    # STEP 0: Check if sensor script exists                                 
    if not os.path.isfile(SENSOR_SCRIPT):                                              
        log(f"[ERROR] Sensor script not found: {SENSOR_SCRIPT}")            
        log("[FAIL] Test aborted due to missing script.")                   
        return False                                                             
                                                                                       
    log(f"[STEP 1] Reading vibration/IMU sensor data {NUM_READS} times...")          
                                                                                     
    readings = []                                                                      
                                                                                     
    for i in range(NUM_READS):                                                         
        output, error = run_local_command(f"python3 {SENSOR_SCRIPT}")                  
        if error:                                                                    
            log(f"[ERROR] Sensor command STDERR (iteration {i+1}): {error}")     
            return False                                                               
                                                                             
        log(f"[INFO] Raw Sensor Data (iteration {i+1}):")                              
        print(output)                                                                  
                                                                             
        try:                                                                           
            gyro_data, accel_data = parse_sensor_data(output)                          
            log(f"[PARSED] Iteration {i+1} ... Gyro: {gyro_data}, Accel: {accel_data}")
            readings.append((gyro_data, accel_data))                                 
        except Exception as e:                                                   
            log(f"[ERROR] Iteration {i+1} failed to parse sensor data: {str(e)}")      
            return False                                                             
                                                               
    # STEP 2: Compare readings to ensure they are not identical                      
    first_read = readings[0]                                                         
    all_identical = all(r == first_read for r in readings)
                                                                                     
    if all_identical:                                                                
        log("[FAIL] All vibration readings are identical ... no variation detected.")
        return False                                                                   
    else:                                                                    
        log("[PASS] Vibration readings show variation across samples.")              
        return True                
        
if __name__ == "__main__":                                                   
    success = verify_vibration_data()                                      
    if success:                                                              
        log("[RESULT] SUCCESS ... Vibration/IMU sensor verification passed.")
        sys.exit(0)                                                          
    else:                                                                    
        log("[RESULT] FAILURE ... Vibration/IMU sensor verification failed.")          
        sys.exit(1)     
