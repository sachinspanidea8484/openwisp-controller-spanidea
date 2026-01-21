"""
VRF Operations via MQTT - Multi-Device Support
✅ Uses device_id for BB device
✅ Uses IP address for PE2, CE1, CE2 devices
✅ Filters responses by execution_id
"""
import paho.mqtt.client as mqtt
import json
import time
import threading
from robot.api.deco import keyword
from robot.libraries.BuiltIn import BuiltIn
import os
 
EXIT_SUCCESS = 0
EXIT_FAILED = 1 
# ===== CONFIGURATION =====
MQTT_BROKER = os.getenv("MQTT_BROKER_IP", "192.168.229.254")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
COMMAND_TIMEOUT = 60
 
# ===== GLOBAL STATE =====
_mqtt_client = None
_primary_device_id = None
_execution_id = None
_subscribed_devices = set()
_response = None
_response_ready = threading.Event()
_response_lock = threading.Lock()
 
 
# ===== LOGGING =====
def _log(message, level="INFO"):
    """Log to console and custom file"""
    BuiltIn().log_to_console(f"[MQTT-VRF] {message}")
    try:
        BuiltIn().run_keyword("Log Message To Custom File", f"[{level}] [MQTT-VRF] {message}")
    except:
        pass
 
 
# ===== MQTT CALLBACKS =====
def _on_connect(client, userdata, flags, rc):
    """Callback when connected to broker"""
    global _subscribed_devices
    
    if rc == 0:
        _log("✅ Connected to MQTT Broker")
        
        if _primary_device_id:
            topic = f"device/{_primary_device_id}/response"
            client.subscribe(topic)
            _subscribed_devices.add(_primary_device_id)
            _log(f"📥 Subscribed to: {topic}")
    else:
        _log(f"❌ Connection failed: {rc}", "ERROR")
 
 
def _on_message(client, userdata, msg):
    """Callback when response received"""
    global _response, _response_ready
    
    try:
        response_data = json.loads(msg.payload.decode())
        
        response_exec_id = response_data.get("execution_id", "")
        normalized_response_exec = str(response_exec_id).replace('-', '')
        normalized_current_exec = str(_execution_id).replace('-', '')
        
        if normalized_response_exec != normalized_current_exec:
            _log(f"⚠️ Ignoring response for execution_id: {response_exec_id}")
            return
        
        with _response_lock:
            _response = response_data
            _log(f"📨 Response received (exit_code: {_response.get('exit_code', -1)})")
            _response_ready.set()
            
    except Exception as e:
        _log(f"⚠️ Parse error: {str(e)}", "ERROR")
        with _response_lock:
            _response = {'stdout': '', 'stderr': str(e), 'exit_code': -1}
            _response_ready.set()
 
 
def _subscribe_to_device(device_id):
    """Subscribe to additional device response topic"""
    global _mqtt_client, _subscribed_devices
    
    if not _mqtt_client:
        return
    
    normalized_id = str(device_id)
    
    if normalized_id not in _subscribed_devices:
        topic = f"device/{normalized_id}/response"
        _mqtt_client.subscribe(topic)
        _subscribed_devices.add(normalized_id)
        _log(f"📥 Subscribed to device: {topic}")
 
 
# ===== CONNECTION MANAGEMENT =====
def _mqtt_connect(device_id, execution_id):
    """Establish MQTT connection"""
    global _mqtt_client, _primary_device_id, _execution_id, _subscribed_devices
    
    if _mqtt_client is not None:
        return
    
    _primary_device_id = str(device_id)
    _execution_id = str(execution_id).replace('-', '')
    
    _log(f"🔌 Connecting to MQTT Broker {MQTT_BROKER}:{MQTT_PORT}")
    _log(f"📋 Primary Device ID: {_primary_device_id}")
    _log(f"📋 Execution ID: {_execution_id}")
    
    try:
        _mqtt_client = mqtt.Client(client_id=f"robot_vrf_{_execution_id}")
        _mqtt_client.on_connect = _on_connect
        _mqtt_client.on_message = _on_message
        _mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        _mqtt_client.loop_start()
        time.sleep(2)
        _log("✅ MQTT connection ready")
    except Exception as e:
        _log(f"❌ Connection failed: {str(e)}", "ERROR")
        raise Exception(f"MQTT connection failed: {str(e)}")
 
 
def _mqtt_disconnect():
    """Close MQTT connection"""
    global _mqtt_client, _subscribed_devices
    if _mqtt_client:
        _mqtt_client.loop_stop()
        _mqtt_client.disconnect()
        _mqtt_client = None
        _subscribed_devices.clear()
        _log("🔌 Disconnected from MQTT broker")
 
 
# ===== COMMAND EXECUTION =====
def _get_target_device_id(device):
    """
    Get target device ID based on device configuration
    - For BB: use device_id
    - For PE2, CE1, CE2: use ip
    """
    # Check if this is BB device (has device_id)
    if "device_id" in device:
        target_id = device["device_id"]
        _log(f"Using device_id: {target_id} for BB device")
        return target_id
    
    # For PE2, CE1, CE2: use ip address
    target_id = device.get("ip", "unknown")
    _log(f"Using IP: {target_id} for device")
    return target_id
 
 
def _run_command_mqtt(command, device, timeout=COMMAND_TIMEOUT):
    """
    Execute command via MQTT on specific device
    
    Args:
        command: Shell command to execute
        device: Device dict with device_id (for BB) or ip (for others)
        timeout: Command timeout in seconds
    
    Returns:
        dict: Response with stdout, stderr, exit_code
    """
    global _mqtt_client, _response, _response_ready
    
    if not _mqtt_client:
        raise Exception("MQTT not connected. Call 'MQTT Initialize Connection' first.")
    
    # Get target device ID (device_id for BB, uuid for others)
    target_device_id = _get_target_device_id(device)
    
    # Subscribe to target device
    _subscribe_to_device(target_device_id)
    
    _log(f"📤 Sending command to device {target_device_id}: {command[:80]}...")
    
    # Reset response state
    with _response_lock:
        _response = None
    _response_ready.clear()
    
    # Build command topic
    command_topic = f"device/{target_device_id}/command"
    
    payload = {
        "command": command,
        "execution_id": _execution_id,
        "timestamp": time.time()
    }
    
    try:
        # Send command
        _mqtt_client.publish(command_topic, json.dumps(payload), qos=1)
        _log(f"✅ Command sent to: {command_topic}")
        
        # Wait for response
        _log(f"⏳ Waiting for response (timeout: {timeout}s)...")
        got_response = _response_ready.wait(timeout=timeout)
        
        if not got_response:
            _log(f"❌ Timeout after {timeout}s", "ERROR")
            return {'stdout': '', 'stderr': 'Command timeout', 'exit_code': -1}
        
        # Get response safely
        with _response_lock:
            result = _response.copy() if _response else {'stdout': '', 'stderr': 'No response', 'exit_code': -1}
        
        _log(f"✅ Command completed (exit_code: {result.get('exit_code', -1)})")
        
        return result
        
    except Exception as e:
        _log(f"❌ Command failed: {str(e)}", "ERROR")
        raise Exception(f"MQTT command execution failed: {str(e)}")
 
 
# ===== ROBOT FRAMEWORK KEYWORDS =====
 
@keyword
def mqtt_initialize_connection(device_id, execution_id):
    """
    Initialize MQTT connection for VRF tests
    
    Args:
        device_id: Primary device ID (BB device_id)
        execution_id: Unique execution identifier
    """
    _mqtt_connect(device_id, execution_id)
 
 
@keyword
def mqtt_close_connection():
    """Close MQTT connection"""
    _mqtt_disconnect()
 
 
@keyword
def mqtt_get_frr_config(device):
    """
    Fetch FRR configuration from device
    
    Args:
        device: Device dict with device_id (BB) or ip (PE2/CE1/CE2)
    """
    _log(f"Fetching FRR config from device {device.get('ip', 'unknown')}")
    
    cmd = "cat /etc/frr/frr.conf"
    result = _run_command_mqtt(cmd, device)
    
    output = result.get('stdout', '')
    if output.strip():
        _log(f"FRR Config:\n{output[:200]}...")
    
    return output
 
# def mqtt_get_frr_config(self, device):
#     _log(f"Fetching FRR config from device {device.get('ip', 'unknown')}")
 
#     user = device.get("user", "")
 
#     # If user is root → no sudo
#     if user == "root":
#         cmd = "cat /etc/frr/frr.conf"
#     else:
#         # Use sudo without prompting
#         cmd = "sudo cat /etc/frr/frr.conf"
 
#     # Execute via MQTT
#     result = _run_command_mqtt(cmd, device)
 
#     return result
 
 
@keyword
def mqtt_check_vrf_established(device):
    """
    Check if VRF/BGP is established on device
    
    Args:
        device: Device dict with device_id (BB) or ip (PE2)
    
    Returns:
        bool: True if VRF is established
    """
    _log(f"Checking VRF/BGP status on device {device.get('ip', 'unknown')}")
    
    cmd = "vtysh -c 'show bgp vrf vrf1 neighbors'"
    result = _run_command_mqtt(cmd, device)
    
    output = result.get('stdout', '')
    established = "Established" in output
    
    _log(f"VRF Established: {established}")
    
    return established
 
 
@keyword
def mqtt_create_vrf(device):
    """
    Create VRF configuration on device
    
    Args:
        device: Device dict with interface, vrf_ip, and device_id (BB) or ip (PE2)
    """
    iface = device.get("interface")
    vrf_ip = device.get("vrf_ip")
    
    if not iface or not vrf_ip:
        _log(f"⚠️ Missing interface or vrf_ip in device config", "WARN")
        raise ValueError(f"Device missing 'interface' or 'vrf_ip'")
    
    _log(f"Creating VRF on device {device.get('ip', 'unknown')} (iface={iface}, ip={vrf_ip})")
    
    commands = [
        "ip link add vrf1 type vrf table 10 || true",
        "ip link set dev vrf1 up",
        f"ip link set dev {iface} master vrf1",
        f"ip addr flush dev {iface}",
        f"ip addr add {vrf_ip} dev {iface}",
        f"ip link set dev {iface} up"
    ]
    
    for cmd in commands:
        _log(f"Executing: {cmd}")
        result = _run_command_mqtt(cmd, device)
        
        if result.get('exit_code', 0) != 0:
            stderr = result.get('stderr', '')
            if stderr and 'File exists' not in stderr:
                _log(f"⚠️ Command warning: {stderr}", "WARN")
        
        time.sleep(1)
    
    _log(f"✅ VRF created on device")
 
 
@keyword
def mqtt_restart_frr(device):
    """
    Restart FRR service on device
    
    Args:
        device: Device dict with device_id (BB) or ip (PE2)
    """
    _log(f"Restarting FRR on device {device.get('ip', 'unknown')}")
    
    cmd = "systemctl restart frr || /etc/init.d/frr restart"
    result = _run_command_mqtt(cmd, device)
    
    time.sleep(5)
    
    _log(f"✅ FRR restarted")
 
 
# @keyword
# def mqtt_ping_test(device, target):
#     """
#     Test ping connectivity from device to target
    
#     Args:
#         device: Source device dict with device_id (BB) or ip (CE1/CE2)
#         target: Target IP address to ping
    
#     Returns:
#         bool: True if ping successful
#     """
#     _log(f"Pinging {target} from device {device.get('ip', 'unknown')}")
    
#     cmd = f"ping -c 4 {target}"
#     result = _run_command_mqtt(cmd, device)
#     log(f"✅ Ping successful>>> → {result}")
 
    
#     output = result.get('stdout', '')
#     success = (" 0% packet loss" in output) or (" 4 received" in output)
    
#     if success:
#         _log(f"✅ Ping successful → {target}")
#     else:
#         _log(f"❌ Ping failed → {target}", "WARN")
    
#     return success
 


@keyword
def mqtt_ping_test(device, target):
    """
    Test ping connectivity from device to target
    """
    _log(f"Pinging {target} from device {device.get('ip', 'unknown')}")
    
    cmd = f"ping -c 4 {target}"
    result = _run_command_mqtt(cmd, device)

    # FIXED logging
    _log(f"✅ Ping raw result → {result}")

    output = result.get('stdout', '')
    success = (" 0% packet loss" in output) or (" 4 received" in output)
    
    if success:
        _log(f"✅ Ping successful → {target}")
    else:
        _log(f"❌ Ping failed → {target}", "WARN")
    
    return success

