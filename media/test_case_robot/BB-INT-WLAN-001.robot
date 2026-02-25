*** Settings ***
Library           ../../../resources/keywords/BB-INT-WLAN-001.py
Library           ../../../resources/keywords/execution/connection_manager.py
Library           JSONLibrary
Library           OperatingSystem
Library           SSHLibrary
Library           BuiltIn
Library           Collections
Library           String
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
WiFi LAN Performance Test (Dynamic)
    [Documentation]    Full Wi-Fi performance validation per BB-INT-WLAN-002
    [Tags]    BB-INT-WLAN-001

    # ---------------- FETCH & VALIDATE IPs ----------------
    Fetch And Validate RPi Interface IPs    ${PC_LIST}    ${INTERFACE}
    # ---------------- CONFIGURE TEMP STATIC IPs ----------------
    Build Static IP Map    ${PC_LIST}    ${INTERFACE}
    Configure Static IP Temporarily    ${PC_LIST}    ${INTERFACE}    ${STATIC_IP}

    # ---------------- BASELINE STATS ----------------
    Ping All Devices Using Interface         ${PC_LIST}    ${INTERFACE}

    # ---------------- SET EPHEMERAL PORT RANGE ----------------
#    Set Ephemeral Port Range    ${PC_LIST}    45220    45225
    Set Ephemeral Port Range    ${PC_LIST}     ${START_PORT}    ${END_PORT}

    # ---------------- RUN IPERF ----------------
    Set Iperf Port Range    ${START_PORT}    ${END_PORT}

    Run Full Mesh Iperf Test

    # ---------------- POST-IPERF STATS ----------------
    Capture Ifconfig Snapshot For Devices    ${PC_LIST}    ${INTERFACE}
    Validate Ifconfig Errors For Devices     ${PC_LIST}    ${INTERFACE}
    Ping All Devices Using Interface         ${PC_LIST}    ${INTERFACE}

    # ---------------- RESTORE ORIGINAL IPs ----------------
#    Restore Original IP    ${PC_LIST}    ${INTERFACE}    ${ORIGINAL_IPS}
    Enable DHCP On Interface    ${PC_LIST}    ${INTERFACE}

    Log                ==== Completed WiFi LAN Performance Test ====


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

Run Full Mesh Iperf Test
    Log     Running full-mesh IPERF iperf3 test

    Ensure Iperf3 On All PCs    ${PC_LIST}
    Start Iperf Servers Dynamic   ${PC_LIST}

    # Unified monitoring: BEFORE + DURING + AFTER
    Monitor System Stats Around Iperf    ${DUT}    ${DURATION}

    Run Full Mesh Iperf Dynamic
    ...    ${PC_LIST}
    ...    ${DURATION}
    ...    ${BANDWIDTH}
    ...    ${INTERFACE}

    Wait For All Iperf Clients

    # Ensure monitoring completes AFTER iperf
    Wait For Monitoring To Finish








