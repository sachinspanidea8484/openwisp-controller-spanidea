import subprocess                                       
import time                                              
from datetime import datetime                           
import sys                                                       
# -------------------------------------------------------                
# CONFIGURATION                    
# -------------------------------------------------------    
RESET_CMD = "fpga-io -w 0x03 0x01"                       
WAIT_AFTER_RESET = 10          # seconds to wait after triggering reset
MAX_REBOOT_WAIT = 180          # max time to wait for system to come back

# -------------------------------------------------------       
# UTILITIES                                                      
# -------------------------------------------------------
def log(msg):                                                    
    timestamp = datetime.now().strftime("[%Y%m%d-%H%M%S]")
    print(f"{timestamp} {msg}")                          

def run_cmd(cmd, timeout=10):                                        
    try:                                                           
        proc = subprocess.Popen(                
            cmd,                                                 
            shell=True,                                         
            stdout=subprocess.PIPE,                      
            stderr=subprocess.PIPE,                             
            text=True                                    
        )                                            
        out, err = proc.communicate(timeout=timeout)
        return out.strip(), err.strip(), proc.returncode             
    except subprocess.TimeoutExpired:                        
        return "", "Timeout", 1           

def wait_for_reboot():                                                   
    """                                                                  
    Waits for system reboot by monitoring /proc/uptime reset.            
    """                                                                  
    log("[INFO] Waiting for system reboot...")                           
    try:                                                                 
        with open("/proc/uptime", "r") as f:                             
            old_uptime = float(f.read().split()[0])                      
    except:                                                              
        log("[ERROR] Unable to read system uptime before reset.")        
        return False                                                     
    start = time.time()                                            
    while time.time() - start < MAX_REBOOT_WAIT:                 
        try:                                                     
            with open("/proc/uptime", "r") as f:                 
                new_uptime = float(f.read().split()[0])          
            if new_uptime < old_uptime:                          
                log("[OK] System reboot detected successfully.") 
                return True                                          
        except:                                                  
            # During reboot, file may be inaccessible            
            pass                                                 
        time.sleep(2)                                            
    log("[ERROR] System reboot not detected within expected time.")
    return False                                                   

# -------------------------------------------------------          
# MAIN TEST LOGIC (BB-SU-007)                                      
# -------------------------------------------------------          
def main():                                                        
    log("[STEP] Starting System Reset Verification Test (BB-SU-007)")
    # Step 1: Execute system reset command                           
    log("[STEP] Executing system reset command...")                  
    out, err, rc = run_cmd(RESET_CMD)                                
    if rc != 0:                                                      
        log(f"[ERROR] Reset command not found : {err}")              
        sys.exit(1)                                                  
    log("[OK] Reset command executed. System reboot initiated.")     
    # Step 2: Initial wait                                           
    time.sleep(WAIT_AFTER_RESET)                                     
    # Step 3: Verify reboot occurred                                 
    if not wait_for_reboot():                                        
        log("[FAILED] System reboot verification failed.")           
        sys.exit(1)                                                  
    log("=== TEST RESULT: PASS (BB-SU-007 System Reset Verified) ===")

if __name__ == "__main__":                                            
    main()             