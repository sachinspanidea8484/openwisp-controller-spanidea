*** Settings ***
Library           ../../../resources/keywords/BB-INT-WLAN-003.py
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
BB-INT-WLAN-003 Full WiFi LAN Performance Test
    [Documentation]    Full BB-INT-WLAN-003 flow
    [Tags]    BB-INT-WLAN-003

    Log Message To Custom File    ===== STEP 1: Detect Active Interfaces =====

    Fetch And Validate RPi Interface IPs    ${PC_LIST}    ${INTERFACE}

    Log Message To Custom File    ===== STEP 2: Management Ping Check =====

    Ping All Devices Using Interface         ${PC_LIST}    ${INTERFACE}

    Log    ========= set iperf port =============
    Set Iperf Port Range        ${START_PORT}    ${END_PORT}

    Log Message To Custom File    ===== STEP 5: Run Directed ETH1 IPERF Tests =====

    Run Directed Iperf Tests PC ↔ BB    ${PC_LIST}    ${DUT}    ${DURATION}    ${BANDWIDTH}    ${INTERFACE}

    Log Message To Custom File    ===== STEP 7: Capture IFCONFIG After =====
    Capture Ifconfig Snapshot For Devices    ${PC_LIST}    ${INTERFACE}

    Log Message To Custom File    ===== STEP 8: Validate IFCONFIG Errors =====
    Validate Ifconfig Errors For Devices     ${PC_LIST}    ${INTERFACE}

    Log Message To Custom File    ===== STEP 9: Post Ping Check =====
    Ping All Devices Using Interface         ${PC_LIST}    ${INTERFACE}

    Log Message To Custom File    ===== TEST COMPLETED SUCCESSFULLY =====

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

    # ================= DUT =================
    ${DUT}=          Set Variable    ${device_config["BB"]}
    ${dut_ip}=       Set Variable    ${DUT["ip"]}
    ${dut_user}=     Set Variable    ${DUT["user"]}
    ${dut_pass}=     Set Variable    ${DUT["password"]}
    ${dut_dev_id}=   Set Variable    ${DUT.get("device_id", "2001")}
    ${dut_exec_id}=  Set Variable    ${DUT.get("execution_id", "1")}
    ${protocol}=     Set Variable    ${DUT.get("connection_protocol", "SSH")}

    # ================= TEST PARAMS =================
    ${DURATION}=    Set Variable    ${test_config["duration"]}
    ${BANDWIDTH}=   Set Variable    ${test_config["bandwidth"]}
    ${INTERFACE}=   Set Variable    ${test_config["interface"]}
    ${START_PORT}=  Set Variable    ${test_config["start_port"]}
    ${END_PORT}=    Set Variable    ${test_config["end_port"]}


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
    Set Suite Variable    ${DUT}    ${dut_device}
    Set Suite Variable    ${dut_ip}
    Set Suite Variable    ${DURATION}
    Set Suite Variable    ${BANDWIDTH}
    Set Suite Variable    ${INTERFACE}
    Set Suite Variable    ${START_PORT}
    Set Suite Variable    ${END_PORT}
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


Capture Baseline Stats
    Log Message To Custom File    Capturing baseline system stats on DUT
    Capture System Stats    ${DUT}    baseline


Run Full Mesh Iperf Test
    Log Message To Custom File    Running full-mesh IPERF iperf3 test

    Ensure Iperf3 On All PCs    ${PC_LIST}
    Start Iperf Servers Dynamic   ${PC_LIST}

    Monitor System Stats Around Iperf    ${DUT}    ${DURATION}

    Run Full Mesh Iperf Dynamic
    ...    ${PC_LIST}
    ...    ${DURATION}
    ...    ${BANDWIDTH}
    ...    ${INTERFACE}

    Wait For All Iperf Clients
    Wait For Monitoring To Finish
