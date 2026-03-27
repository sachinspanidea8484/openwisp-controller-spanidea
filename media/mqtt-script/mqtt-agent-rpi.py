#!/usr/bin/env python3
"""
MQTT Device Agent for OpenWrt
Listens for commands and executes them sequentially

IMPORTANT: Update these values before running:
- DEVICE_ID: Your device identifier (must match Robot Framework)
- BROKER_HOST: MQTT broker IP address

NOTE: execution_id is passed with each command (not in topic)
"""

import paho.mqtt.client as mqtt
import json
import subprocess
import sys
from datetime import datetime


# ===== CONFIGURATION - UPDATE THESE =====
DEVICE_ID = "coeNzYP0sFvBTdQYmy6Ahk504szIA81x"      # Change to match your device
BROKER_HOST = "44.199.94.165"                       # MQTT broker IP
BROKER_PORT = 1883
# =========================================

COMMAND_TOPIC = f"device/{DEVICE_ID}/command"
RESPONSE_TOPIC = f"device/{DEVICE_ID}/response"


def log(message):
    """Print timestamped log message"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[{timestamp}] {message}")
    sys.stdout.flush()


def execute_command(command):
    """
    Execute shell command and return result.
    BLOCKING - waits for command to complete before returning.
    """
    log(f"Executing: {command}")

    try:
        result = subprocess.run(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
            text=True
        )

        response = {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
            "timestamp": datetime.now().isoformat()
        }

        log(f"Command completed (exit_code: {result.returncode})")

        if result.stdout:
            log(f"   Output: {result.stdout[:100]}...")
        if result.stderr:
            log(f"   Error: {result.stderr[:100]}...")

        return response

    except subprocess.TimeoutExpired:
        log("Command timeout (60s)")
        return {
            "stdout": "",
            "stderr": "Command timeout after 60 seconds",
            "exit_code": -1,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        log(f"Execution error: {str(e)}")
        return {
            "stdout": "",
            "stderr": str(e),
            "exit_code": -1,
            "timestamp": datetime.now().isoformat()
        }


def on_connect(client, userdata, flags, rc):
    """Callback when connected to broker"""
    if rc == 0:
        log("Connected to MQTT Broker")
        log(f"Subscribing to: {COMMAND_TOPIC}")
        client.subscribe(COMMAND_TOPIC)
        log("Listening for commands...")
    else:
        log(f"Connection failed with code {rc}")


def on_message(client, userdata, msg):
    """
    Callback when command received.
    Extracts execution_id from payload and includes in response.
    """
    try:
        log("")
        log("=" * 70)
        log("New command received")

        payload = json.loads(msg.payload.decode())
        command = payload.get("command", "")
        execution_id = payload.get("execution_id", "unknown")

        if not command:
            log("No command in payload")
            return

        log(f"Command: {command}")
        log(f"Execution ID: {execution_id}")

        result = execute_command(command)
        result["execution_id"] = execution_id

        response_json = json.dumps(result)
        client.publish(RESPONSE_TOPIC, response_json, qos=1)

        log(f"Response sent to: {RESPONSE_TOPIC}")
        log(f"   Execution ID: {execution_id}")
        log("=" * 70)
        log("")

    except json.JSONDecodeError as e:
        log(f"Invalid JSON: {str(e)}")
    except Exception as e:
        log(f"Error processing message: {str(e)}")


def on_disconnect(client, userdata, rc):
    """Callback when disconnected"""
    if rc != 0:
        log("Unexpected disconnection - attempting to reconnect...")
    else:
        log("Disconnected gracefully")


def main():
    """Start MQTT client and listen for commands"""
    print("\n" + "=" * 70)
    log("MQTT Device Agent Starting")
    log(f"Device ID: {DEVICE_ID}")
    log(f"Broker: {BROKER_HOST}:{BROKER_PORT}")
    log(f"Command Topic: {COMMAND_TOPIC}")
    log(f"Response Topic: {RESPONSE_TOPIC}")
    log("Execution ID will be extracted from each command payload")
    print("=" * 70 + "\n")

    client_id = f"device_{DEVICE_ID}"
    client = mqtt.Client(client_id=client_id)

    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect

    client.reconnect_delay_set(min_delay=1, max_delay=60)

    try:
        log("Connecting to broker...")
        client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
        client.loop_forever()

    except KeyboardInterrupt:
        log("\nShutdown signal received")
        log("Disconnecting...")
        client.disconnect()
        log("Agent stopped")
        sys.exit(0)

    except Exception as e:
        log(f"Fatal error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()