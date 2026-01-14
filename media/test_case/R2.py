def _log(message, level="INFO"):
    """Log to console and custom file"""
    BuiltIn().log_to_console(f"[MQTT-VRF] {message}")
    try:
        BuiltIn().run_keyword("Log Message To Custom File", f"[{level}] [MQTT-VRF] {message}")
    except:
        pass
