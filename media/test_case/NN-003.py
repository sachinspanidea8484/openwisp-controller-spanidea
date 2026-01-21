
import paramiko
import time
from robot.libraries.BuiltIn import BuiltIn
 
def log_message(msg, level="INFO"):
    BuiltIn().log_to_console(msg)
    try:
        BuiltIn().run_keyword("Log Message To Custom File", f"[{level}] {msg}")
    except Exception:
        pass
 
class VRF:
    ROBOT_LIBRARY_SCOPE = "GLOBAL"
 
    def ssh_run(self, host, user, password, cmd, timeout=30):
        log_message(f"[{host}] Running: {cmd}")
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname=host, username=user, password=password, timeout=timeout)
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
        output = stdout.read().decode()
        error = stderr.read().decode()
        ssh.close()
        if output.strip():
            log_message(f"[{host}] OUTPUT:\n{output}")
        if error.strip():
            log_message(f"[{host}] ERROR:\n{error}", "WARN")
        return output + error
 
 
    # ---------- FRR CONFIG ----------
    def get_frr_config(self, device):
        log_message(f"Fetching FRR config from {device['ip']}")
        cmd = "cat /etc/frr/frr.conf"
        return self.ssh_run(device["ip"], device["user"], device["password"], cmd)
 
    
    def get_frr_config(self, device):
        log_message(f"Fetching FRR config from {device['ip']}")
    
        user = device.get("user", "")
    
    # If user is root → no sudo
        if user == "root":
            cmd = "cat /etc/frr/frr.conf"
        else:
        # Use sudo without prompting for password
            cmd = "sudo cat /etc/frr/frr.conf"
    
        return self.ssh_run(
            device["ip"],
            device["user"],
            device["password"],
            cmd
       )
 
 
    # def get_frr_config(self, device):
    # log_message(f"Fetching FRR config from {device.get('ip')}")
 
    # user = device.get("user", "")
 
    # # Detect lightweight OS like OpenWrt
    # os_check = self.ssh_run(
    #     device["ip"],
    #     device["user"],
    #     device["password"],
    #     "uname -a"
    # )
 
    # if user == "root" or "OpenWrt" in os_check:
    #     cmd = "cat /etc/frr/frr.conf"
    # else:
    #     cmd = "sudo -S cat /etc/frr/frr.conf"
 
    # return self.ssh_run(
    #     device["ip"],
    #     device["user"],
    #     device["password"],
    #     cmd
    # )
 
 
 
    # ---------- VRF CHECK ----------
    def check_vrf_established(self, device):
        log_message(f"Checking VRF/BGP status on {device['ip']}")
        cmd = "vtysh -c 'show bgp vrf vrf1 neighbors'"
        out = self.ssh_run(device["ip"], device["user"], device["password"], cmd)
 
        established = "Established" in out
        log_message(f"[{device['ip']}] VRF Established: {established}")
 
        return established
 
    # ---------- CREATE VRF ----------
    def create_vrf(self, device):
        log_message(f"Creating VRF on {device['ip']}")
 
        iface = device.get("interface")
        vrf_ip = device.get("vrf_ip")
 
        if not iface or not vrf_ip:
            log_message(f"Missing interface or vrf_ip in device: {device}", "WARN")
            return
 
        cmds = [
            "ip link add vrf1 type vrf table 10 || true",
            "ip link set dev vrf1 up",
            f"ip link set dev {iface} master vrf1",
            f"ip addr flush dev {iface}",
            f"ip addr add {vrf_ip} dev {iface}",
            f"ip link set dev {iface} up"
        ]
 
        for cmd in cmds:
            self.ssh_run(device["ip"], device["user"], device["password"], cmd)
            time.sleep(1)
 
        log_message(f"VRF created on {device['ip']}")
 
    # ---------- RESTART FRR ----------
    def restart_frr(self, device):
        log_message(f"Restarting FRR on {device['ip']}")
        cmd = "systemctl restart frr || /etc/init.d/frr restart"
        self.ssh_run(device["ip"], device["user"], device["password"], cmd)
        time.sleep(5)
        log_message(f"FRR restarted on {device['ip']}")
 
    # ---------- PING TEST ----------
    def ping_test(self, device, target):
        log_message(f"Pinging {target} from {device['ip']}")
        cmd = f"ping -c 4 {target}"
        out = self.ssh_run(device["ip"], device["user"], device["password"], cmd)
 
        success = (" 0% packet loss" in out) or (" 4 received" in out)
        if success:
            log_message(f"Ping successful from {device['ip']} → {target}")
        else:
            log_message(f"Ping failed from {device['ip']} → {target}", "WARN")
 
        return success
 
