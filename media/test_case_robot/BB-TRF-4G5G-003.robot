*** Settings ***
Library           ../../../resources/keywords/BB-TRF-4G5G-003.py
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
BB-TRF-4G5G-003 End-to-End Validation
    [Documentation]    End-to-end modem + WiFi + RPi connectivity validation
    [Tags]    BB-TRF-4G5G-003

    Log To Console                ===== START Wi-Fi AP LAN <--> 4G/5G WAN END-TO-END TEST =====
    Log Message To Custom File    ===== START Wi-Fi AP LAN <--> 4G/5G WAN END-TO-END TEST =====


    Log Message To Custom File    ==== Ensuring Modem & Default Route ====

    ${modem_ip}=    Ensure Modem Connected        DUT    ${dut_interface}
    Set Suite Variable    ${modem_ip}
    Ensure WWAN Default Route     DUT    ${dut_interface}   ${modem_ip}

    Log Message To Custom File    ==== Configuring Wi-Fi AP ====

    Setup WiFi AP    DUT    ${WIFI_LIST}

    Log Message To Custom File    ==== Connecting RPis To Wi-Fi ====

    Connect RPi To WiFi    ${PC_LIST}    ${WIFI_LIST}

    Log Message To Custom File    ==== Check RPis Routing ====
    Check RPi Routing Dynamic    ${PC_LIST}    ${pc_interface}

    Log Message To Custom File    ==== Starting Traffic & System Metrics ====

    # Start Moniter System Stats    ${dut_device}    ${metrics_interval}
    Monitor System Stats Around Iperf    ${dut_device}    ${metrics_interval}

    Ping All RPis   ${PC_LIST}   ${remote_ping_ip}    ${pc_interface}

    Log Message To Custom File    ==== Stopping Metrics & Cleaning Routes ====

    # Stop Moniter System Stats
    Wait For Monitoring To Finish
    Cleanup WWAN Default Route    DUT    ${dut_interface}    ${modem_ip}

    Log To Console                ===== END Wi-Fi AP LAN <--> 4G/5G WAN END-TO-END TEST : SUCCESS =====
    Log Message To Custom File    ===== END Wi-Fi AP LAN <--> 4G/5G WAN END-TO-END TEST : SUCCESS =====


*** Keywords ***
# ================= SUITE SETUP =================
Initialize Test Environment
    Initialize Custom Log File
    Load Device Info

    Log To Console    ==== Opening Device Connections ====
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


# ================= SUITE TEARDOWN =================
Cleanup Test Environment
    Log To Console    ==== Closing Device Connections ====
    CLOSE ALL DEVICE CONNECTIONS


# ================= LOAD CONFIG =================
Load Device Info
    Log Message To Custom File    Loading config from provided variables

    Should Not Be Empty    ${DEVICE_JSON}
    Should Not Be Empty    ${TEST_JSON}

    ${device_config}=    Evaluate    json.loads(r'''${DEVICE_JSON}''')    json
    ${test_config}=      Evaluate    json.loads(r'''${TEST_JSON}''')      json
    ${WIFI_LIST}=    Set Variable    ${test_config["wifi"]}


    # ================= DUT =================
    ${DUT}=          Set Variable    ${device_config["BB"]}
    ${dut_ip}=       Set Variable    ${DUT["ip"]}
    ${dut_user}=     Set Variable    ${DUT["user"]}
    ${dut_pass}=     Set Variable    ${DUT["password"]}
    ${dut_dev_id}=   Set Variable    ${DUT.get("device_id", "2001")}
    ${dut_exec_id}=  Set Variable    ${DUT.get("execution_id", "1")}
    ${protocol}=     Set Variable    ${DUT.get("connection_protocol", "SSH")}

    # ================= TEST PARAMS =================
    ${WIFI_LIST}=              Set Variable    ${test_config["wifi"]}

    ${SSID}=                   Set Variable    ${test_config["wifi"][0]["ssid"]}
    ${PASSWORD}=               Set Variable    ${test_config["wifi"][0]["password"]}
    ${ENCRYPTION}=             Set Variable    ${test_config["wifi"][0]["encryption"]}

    ${remote_ping_ip}=         Set Variable    ${test_config["remote_ping_ip"]}
    ${idle_ping_duration}=     Set Variable    ${test_config["idle_ping_duration"]}
    ${test_duration}=          Set Variable    ${test_config["test_duration"]}
    ${metrics_interval}=       Set Variable    ${test_config["metrics_interval"]}
    ${dut_interface}=          Set Variable    ${test_config["dut_interface"]}
    ${pc_interface}=           Set Variable     ${test_config["pc_interface"]}

    ${PC_LIST}=                Set Variable    ${test_config["PC"]}


    # ================= DEVICE LIST =================
    @{DEVICE_LIST}=    Create List

    # --- Add DUT ---
    ${dut_device}=    Create Dictionary
    ...    name=DUT
    ...    protocol=${protocol}
    ...    ip=${dut_ip}
    ...    user=${dut_user}
    ...    pass=${dut_pass}
    ...    device_id=${dut_dev_id}
    ...    execution_id=${dut_exec_id}
    Append To List    ${DEVICE_LIST}    ${dut_device}

     # --- Add ALL PCs ---
    ${PC_LIST}=    Set Variable    ${test_config["PC"]}

    FOR    ${pc}    IN    @{PC_LIST}
        ${pc_device}=    Create Dictionary
        ...    name=${pc["name"]}
        ...    protocol=${protocol}
        ...    ip=${pc["ip"]}
        ...    user=${pc["user"]}
        ...    pass=${pc["password"]}
        ...    device_id=${pc.get("device_id", "2001")}
        ...    execution_id=${pc.get("execution_id", "1")}

        Append To List    ${DEVICE_LIST}    ${pc_device}
    END

    ${DEVICE_COUNT}=    Get Length    ${DEVICE_LIST}
    Set Suite Variable    ${PC_LIST}

    ${all_devices}=    Create List    ${dut_device}

    FOR    ${pc}    IN    @{PC_LIST}
    Append To List    ${all_devices}    ${pc}
    END

    # ================= EXPORT VARIABLES =================
    Set Suite Variable    ${DEVICE_LIST}
    Set Suite Variable    ${PC_LIST}
    Set Suite Variable    ${dut_device}
    Set Suite Variable    ${dut_ip}
    Set Suite Variable    ${WIFI_LIST}
    Set Suite Variable    ${SSID}
    Set Suite Variable    ${PASSWORD}
    Set Suite Variable    ${ENCRYPTION}
    Set Suite Variable    ${remote_ping_ip}
    Set Suite Variable    ${idle_ping_duration}
    Set Suite Variable    ${test_duration}
    Set Suite Variable    ${metrics_interval}
    Set Suite Variable    ${dut_interface}
    Set Suite Variable    ${pc_interface}
    Set Suite Variable    ${CONNECTION_PROTOCOL}    ${protocol}
    Set Suite Variable    ${DEVICE_ID}              ${dut_dev_id}
    Set Suite Variable    ${EXECUTION_ID}           ${dut_exec_id}
    Set Suite Variable    ${ALL_DEVICES}   ${all_devices}


    Log To Console    ------------------------------------------------------------
    Log To Console    Configuration Loaded:
    Log To Console    - Protocol: ${CONNECTION_PROTOCOL}
    Log To Console    - DUT IP: ${dut_ip}
    Log To Console    - Device ID: ${DEVICE_ID}
    Log To Console    - Execution ID: ${EXECUTION_ID}
    Log To Console    - Devices Loaded: ${DEVICE_COUNT}
    Log To Console    ------------------------------------------------------------





 