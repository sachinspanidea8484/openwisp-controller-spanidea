*** Settings ***
Library           ../../../resources/keywords/BB-TRF-4G5G-002.py
Library           ../../../resources/keywords/execution/connection_manager.py
Library           OperatingSystem
Library           JSONLibrary
Library           Collections
Library           String
Library           BuiltIn
Resource          ../../../resources/keywords/common_keywords.robot

Suite Setup       Initialize Test Environment
Suite Teardown    Cleanup Test Environment

*** Variables ***
${DEVICE_JSON}          ${EMPTY}
${TEST_JSON}            ${EMPTY}
${LOG_FOLDER}           ${CURDIR}/../../../logs
${CONNECTION_PROTOCOL}  SSH
${DEVICE_ID}            ${EMPTY}
${EXECUTION_ID}         ${EMPTY}

*** Test Cases ***
BB-TRF-4G5G-002 4G/5G End-to-End Connectivity Test
    [Documentation]    Validate modem + WiFi AP+ RPi routing and internet access
    [Tags]    BB-TRF-4G5G-002
    Log Message To Custom File    ===== START Wi-Fi LAN <--> 4G/5G WAN END-TO-END TEST =====

    RUN Ensure Modem And Route Ready

    RUN Configure WiFi AP

    RUN Connect RPi To WiFi

    RUN Traffic and System Metrics   

    RUN Verify RPi Connectivity

    RUN Cleanup WWAN Route

  
    Log Message To Custom File    ===== END Wi-Fi LAN <--> 4G/5G WAN END-TO-END TEST : SUCCESS =====

# ============================================================
# SUITE SETUP / TEARDOWN
# ============================================================
*** Keywords ***
Initialize Test Environment
    Initialize Custom Log File
    Load Device Info

    Log Message To Custom File    ==== Opening Device Connections ====
    FOR    ${device}    IN    @{DEVICE_LIST}
        OPEN DEVICE CONNECTION
        ...    ${device["name"]}
        ...    ${device["protocol"]}
        ...    ${device["ip"]}
        ...    ${device["user"]}
        ...    ${device["pass"]}
        ...    ${device["device_id"]}
        ...    ${device["execution_id"]}
    END


Cleanup Test Environment
    Log Message To Custom File    ==== Closing Device Connections ====
    CLOSE ALL DEVICE CONNECTIONS


# ============================================================
# LOAD CONFIGURATION (WWAN FROM TEST_JSON)
# ============================================================
Load Device Info
    Log Message To Custom File    [STEP] Loading configuration from JSON variables

    Run Keyword If    '${DEVICE_JSON}' == '' or '${TEST_JSON}' == ''
    ...    Fail    DEVICE_JSON or TEST_JSON not provided

    ${device_config}=    Evaluate    json.loads(r'''${DEVICE_JSON}''')    json
    ${test_config}=      Evaluate    json.loads(r'''${TEST_JSON}''')      json

    Run Keyword If    'dut_interface' not in ${test_config}
    ...    Fail    dut_interface must be provided inside TEST_JSON

    # ================= DUT =================
    ${DUT}=            Set Variable    ${device_config["BB"]}
    ${dut_ip}=         Set Variable    ${DUT["ip"]}
    ${dut_user}=       Set Variable    ${DUT["user"]}
    ${dut_pass}=       Set Variable    ${DUT["password"]}
    ${dut_dev_id}=     Set Variable    ${DUT.get("device_id", "2001")}
    ${dut_exec_id}=    Set Variable    ${DUT.get("execution_id", "1")}
    ${protocol}=       Set Variable    ${DUT.get("connection_protocol", "SSH")}

    # ================= PC / RPi =================
    ${PC}=             Set Variable    ${test_config["PC"]}
    ${pc_name}=        Set Variable    ${PC["name"]}
    ${pc_ip}=          Set Variable    ${PC["ip"]}
    ${pc_user}=        Set Variable    ${PC["user"]}
    ${pc_pass}=        Set Variable    ${PC["password"]}
    ${pc_dev_id}=      Set Variable    ${PC.get("device_id", "2002")}
    ${pc_exec_id}=     Set Variable    ${PC.get("execution_id", "1")}
    ${pc_protocol}=    Set Variable    ${PC.get("connection_protocol", "SSH")}
    ${wifi_cfg}=       Set Variable    ${test_config["wifi"]}
    
    Set Suite Variable    ${SSID}        ${wifi_cfg["ssid"]}
    Set Suite Variable    ${WIFI_PASS}   ${wifi_cfg["password"]}
    Set Suite Variable    ${WIFI_ENC}    ${wifi_cfg.get("encryption", "psk2")}
    Set Suite Variable    ${dut_interface}  ${test_config["dut_interface"]}

    # ================= TEST PARAMS =================
    ${pc_interface}=            Set Variable    ${test_config["pc_interface"]}
    ${remote_ping_ip}=          Set Variable    ${test_config["remote_ping_ip"]}
    ${metrics_interval}=        Set Variable    ${test_config["metrics_interval"]}
    ${test_duration}=           Set Variable    ${test_config["test_duration"]}
    ${idle_ping_duration}=      Set Variable    ${test_config["idle_ping_duration"]}

    # ================= DEVICE LIST =================
    ${dut_device}=    Create Dictionary
    ...    name=DUT
    ...    protocol=${protocol}
    ...    ip=${dut_ip}
    ...    user=${dut_user}
    ...    pass=${dut_pass}
    ...    device_id=${dut_dev_id}
    ...    execution_id=${dut_exec_id}

    ${pc_device}=    Create Dictionary
    ...    name=${pc_name}
    ...    protocol=${protocol}
    ...    ip=${pc_ip}
    ...    user=${pc_user}
    ...    pass=${pc_pass}
    ...    device_id=${pc_dev_id}
    ...    execution_id=${pc_exec_id}

    @{DEVICE_LIST}=    Create List    ${dut_device}    ${pc_device}
    ${DEVICE_COUNT}=   Get Length    ${DEVICE_LIST}

    # ================= EXPORT =================
    Set Suite Variable    ${DEVICE_LIST}
    Set Suite Variable    ${dut_device}
    Set Suite Variable    ${pc_name}
    Set Suite Variable    ${pc_pass}
    Set Suite Variable    ${pc_interface}
    Set Suite Variable    ${remote_ping_ip}
    Set Suite Variable    ${idle_ping_duration}
    Set Suite Variable    ${test_duration}
    Set Suite Variable    ${metrics_interval}
    Set Suite Variable    ${DUT_NAME}        DUT
    Set Suite Variable    ${DEVICE_ID}       ${dut_dev_id}
    Set Suite Variable    ${EXECUTION_ID}    ${dut_exec_id}
    Set Suite Variable    ${CONNECTION_PROTOCOL}    ${protocol}

    Log To Console    ------------------------------------------------------------
    Log To Console    Configuration Loaded:
    Log To Console    - Protocol: ${CONNECTION_PROTOCOL}
    Log To Console    - DUT IP: ${dut_ip}
    Log To Console    - Device ID: ${DEVICE_ID}
    Log To Console    - Execution ID: ${EXECUTION_ID}
    Log To Console    - Devices Loaded: ${DEVICE_COUNT}
    Log To Console    ------------------------------------------------------------

# ============================================================
# TEST FLOW WRAPPERS
# ============================================================
RUN Ensure Modem And Route Ready
    Log Message To Custom File    ==== Ensuring Modem & Default Route ====

    ${modem_ip}=    Ensure Modem Connected        DUT    ${dut_interface}
    Set Suite Variable    ${modem_ip}
    Ensure WWAN Default Route     DUT    ${dut_interface}   ${modem_ip}
    

RUN Configure WiFi AP
    Log Message To Custom File    ==== Configuring WiFi AP ====
    Setup WiFi AP    ${DUT_NAME}    ${SSID}    ${WIFI_PASS}    ${WIFI_ENC}

RUN Connect RPi To WiFi
    Log Message To Custom File    ==== Connecting RPi To WiFi ====
    Connect RPis To WiFi     ${pc_name}    ${SSID}    ${WIFI_PASS}

RUN Traffic and System Metrics    

    Log Message To Custom File    ==== Starting Traffic & System Metrics ====

    # Start Moniter System Stats    ${dut_device}    ${metrics_interval}
    Monitor System Stats Around Iperf    ${dut_device}    ${metrics_interval}
  

RUN Verify RPi Connectivity
    Log Message To Custom File    ==== Verifying RPi Connectivity ====
    Check RPi Routing Dynamic     ${pc_name}    ${pc_interface}
    Ping All RPis         ${pc_name}    ${pc_interface}    ${remote_ping_ip}    ${idle_ping_duration}
 

RUN Cleanup WWAN Route
    Log Message To Custom File    ==== Stopping Metrics & Cleaning Routes ====

    # Stop Moniter System Stats
    Wait For Monitoring To Finish
    Cleanup WWAN Default Route    DUT    ${dut_interface}    ${modem_ip}
    
 