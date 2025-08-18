import subprocess
import time
import re
import sys

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
    Parses the SA56004_HWMON8 block and returns formatted string.
    """
    # Note: I²C has the Unicode superscript 2 character
    i2c_bus_match = re.search(r"I²C\s+Bus\s*:\s*(\S+)", section)
    i2c_addr_match = re.search(r"I²C\s+Address\s*:\s*(\S+)", section)
    local_temp_match = re.search(r"Local\s+Temp.*?:\s*([\d\.]+)", section)
    remote_temp_match = re.search(r"Remote\s+Temp.*?:\s*([\d\.]+)", section)

    i2c_bus = i2c_bus_match.group(1) if i2c_bus_match else "N/A"
    i2c_addr = i2c_addr_match.group(1) if i2c_addr_match else "N/A"
    local_temp = local_temp_match.group(1) if local_temp_match else "N/A"
    remote_temp = remote_temp_match.group(1) if remote_temp_match else "N/A"

    return (
        f"  I²C Bus               : {i2c_bus}\n"
        f"  I²C Address           : {i2c_addr}\n"
        f"  Local Temp (°C)        : {local_temp}\n"
        f"  Remote Temp (°C)       : {remote_temp}\n"
    )

def verify_cpu_temperature():
    sensor_script = "/usr/bin/sensor_monitor.py"

    print("[STEP 1] Fetching only SA56004_HWMON8 readings locally...\n")

    all_success = True  # Track if all readings succeed

    for i in range(5):
        output, error = run_command(f"python3 {sensor_script}")

        if error:
            print(f"[{i+1}] [ERROR] Sensor command STDERR: {error}\n")
            all_success = False
        else:
            section = extract_hwmon8_section(output)
            if section:
                print(f"[{i+1}] SA56004_HWMON8")
                print(parse_and_format(section))
            else:
                print(f"[{i+1}] [ERROR] SA56004_HWMON8 section not found.\n")
                all_success = False

        time.sleep(120)

    # Final test result
    if all_success:
        print("[RESULT] SUCCESS – All SA56004_HWMON8 readings retrieved successfully.")
        sys.exit(0)
    else:
        print("[RESULT] FAILURE – One or more readings failed to retrieve SA56004_HWMON8 data.")
        sys.exit(1)

if __name__ == "__main__":
    verify_cpu_temperature()

