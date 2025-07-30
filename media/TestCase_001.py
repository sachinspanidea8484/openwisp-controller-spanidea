import sys, os, subprocess,datetime
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Common')))





class CommandError(Exception):
    pass
def run(cmd, check=True, verbose=True, use_os=False):
    if verbose:
        print(f"$ {cmd}")
    if use_os:
        return os.system(cmd)
    result = subprocess.run(cmd, shell=True, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if verbose:
        if result.stdout.strip():
            print(result.stdout.strip())
        if result.stderr.strip():
            print(result.stderr.strip())
    if check and result.returncode != 0:
        raise CommandError(f"Command failed:\n{result.stderr.strip()}")
    return result.stdout.strip(), result.stderr.strip()








def run(cmd, check=True, verbose=True, use_os=False):
    if verbose:
        print(f"$ {cmd}")
    if use_os:
        return os.system(cmd)
    result = subprocess.run(cmd, shell=True, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if verbose:
        if result.stdout.strip():
            print(result.stdout.strip())
        if result.stderr.strip():
            print(result.stderr.strip())
    if check and result.returncode != 0:
        raise CommandError(f"Command failed:\n{result.stderr.strip()}")
    return result.stdout.strip(), result.stderr.strip()













def verify_logread():
    out, err = run("logread | head -n 5")
    assert "log" in out.lower() or out != "", "System logs not found!"
    print("[✓] System logs found.")

def generate_user_logs():
    levels = [
        ("user.debug", "Test debug message"),
        ("user.info", "Test info message"),
        ("user.warning", "Test warning message"),
        ("user.err", "Test error message"),
    ]
    for level, msg in levels:
        run(f'logger -p {level} "{msg}"')
    out, _ = run("logread | tail -n 10")
    assert "Test" in out, "Log messages not captured!"
    print("[✓] User-level logs captured.")

def check_dmesg():
    out, err = run("dmesg | head -n 5")
    assert out != "", "dmesg output missing"
    print("[✓] Kernel logs available.")

def generate_system_log():
    run('logger "Test system log from user"')
    out, _ = run('logread | grep "Test system log"')
    assert "Test system log" in out, "System log not found!"
    print("[✓] System log message verified.")

def generate_kernel_log():
    run('echo "klog test" > /dev/kmsg')
    out, _ = run('dmesg | tail -n 5')
    assert "klog test" in out, "Kernel log not found!"
    print("[✓] Kernel log message verified.")

def check_logd():
    out, _ = run("ps | grep [l]ogd")
    assert "logd" in out, "logd not running"
    print("[✓] logd process is running.")

def induce_kernel_event():
    run("ifconfig eth0 down")
    run("ifconfig eth0 up")
    out, _ = run("dmesg | tail -n 5")
    assert "eth0" in out, "Interface state change not logged"
    print("[✓] Interface state change logged.")

def main():


    try:
        time.sleep(25)
        verify_logread()
        print("[✓] Step 1 passed: logread check")
        
        generate_user_logs()
        print("[✓] Step 2 passed: user logs generation")
        
        check_dmesg()
        print("[✓] Step 3 passed: kernel log read check")
        
        generate_system_log()
        print("[✓] Step 4 passed: system log verification")
        
        generate_kernel_log()
        print("[✓] Step 5 passed: kernel log generation")
        
        check_logd()
        print("[✓] Step 6 passed: logd process verification")
        
        induce_kernel_event()
        print("[✓] Step 7 passed: kernel interface event")

    except AssertionError as ae:
        print(f"[✗] Assertion failed: {ae}")
        sys.exit(1)
    except Exception as e:
        print(f"[✗] Unexpected error: {e}")
        sys.exit(2)

    print("\nAll logging tests passed successfully.")


if __name__ == "__main__":
    main()


