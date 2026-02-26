*** Settings ***
Library           ../../../resources/keywords/BB-TRF-VRF-001.py
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
BB-TRF-VRF-001 VRF End-to-End Automation
    [Tags]    BB-TRF-VRF-001
    Log    ==== Starting VRF Test ====

    # -------- CREATE VRF --------
    CREATE VRF    DUT    ${DUT["vrf_name"]}    ${DUT["table_id"]}    ${DUT["interface"]}    ${DUT["vrf_ip"]}
    CREATE VRF    PE2    ${PE2["vrf_name"]}    ${PE2["table_id"]}    ${PE2["interface"]}    ${PE2["vrf_ip"]}

    # -------- VERIFY VRF --------
    ${dut_vrf}=    CHECK LINUX VRF    DUT    ${DUT["vrf_name"]}
    Should Be True    ${dut_vrf}

    ${pe2_vrf}=    CHECK LINUX VRF    PE2    ${PE2["vrf_name"]}
    Should Be True    ${pe2_vrf}

    # -------- TEST PING --------
    ${p1}=    PING TEST    CE1    ${CE2["ping_target"]}
    Should Be True    ${p1}

    ${p2}=    PING TEST    CE2    ${CE1["ping_target"]}
    Should Be True    ${p2}

    Log    ==== VRF Test Completed Successfully ====
*** Keywords ***
# ================= SUITE SETUP =================
Initialize Test Environment
    Initialize Custom Log File
    Load Device Info

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
    Log     ==== Closing Device Connections ====
    CLOSE ALL DEVICE CONNECTIONS


Load Device Info
    Should Not Be Empty    ${DEVICE_JSON}
    Should Not Be Empty    ${TEST_JSON}

    ${device_config}=    Evaluate    json.loads(r'''${DEVICE_JSON}''')    json
    ${test_config}=      Evaluate    json.loads(r'''${TEST_JSON}''')      json

     # ================= DUT / BB =================
    ${DUT}=          Set Variable    ${device_config["BB"]}
    ${dut_ip}=       Set Variable    ${DUT["ip"]}
    ${dut_user}=     Set Variable    ${DUT["user"]}
    ${dut_pass}=     Set Variable    ${DUT["password"]}
    ${dut_dev_id}=   Set Variable    ${DUT.get("device_id", "2001")}
    ${dut_exec_id}=  Set Variable    ${DUT.get("execution_id", "1")}
    ${protocol}=     Set Variable    ${DUT.get("connection_protocol", "SSH")}

    ${VRF_IP}=     Set Variable    ${test_config["BB"]["vrf_ip"]}
    ${INTERFACE}=  Set Variable    ${test_config["BB"]["interface"]}
    ${VRF_NAME}=   Set Variable    ${test_config["BB"]["vrf_name"]}
    ${TABLE_ID}=   Set Variable    ${test_config["BB"]["table_id"]}
    ${LOCAL_AS}=   Set Variable    ${test_config["BB"]["local_as"]}
    ${REMOTE_AS}=  Set Variable    ${test_config["CE1"]["remote_as"]}
#    ${PING_TARGET}=    Set Variable    ${test_config["ping_target"]}

     Collections.Set To Dictionary    ${DUT}
    ...    vrf_ip=${VRF_IP}
    ...    interface=${INTERFACE}
    ...    vrf_name=${VRF_NAME}
    ...    table_id=${TABLE_ID}
    ...    local_as=${LOCAL_AS}
    ...    remote_as=${REMOTE_AS}


    @{DEVICE_LIST}=    Create List

    # --- Add BB ---
    ${dut_device}=    Create Dictionary
    ...    name=DUT
    ...    protocol=${protocol}
    ...    ip=${dut_ip}
    ...    user=${dut_user}
    ...    pass=${dut_pass}
    ...    device_id=${dut_dev_id}
    ...    execution_id=${dut_exec_id}

    Append To List    ${DEVICE_LIST}    ${dut_device}

    # ================= CE / PE DEVICES =================
    @{PC_NAMES}=    Create List    CE1    CE2    PE2

    FOR    ${pc_name}    IN    @{PC_NAMES}
        ${pc}=    Set Variable    ${test_config["${pc_name}"]}

        ${pc_device}=    Create Dictionary
        ...    name=${pc_name}
        ...    protocol=${protocol}
        ...    ip=${pc["ip"]}
        ...    user=${pc["user"]}
        ...    pass=${pc["password"]}
        ...    device_id=${pc["device_id"]}
        ...    execution_id=${pc["execution_id"]}

        Append To List    ${DEVICE_LIST}    ${pc_device}
    END

    ${DEVICE_COUNT}=    Get Length    ${DEVICE_LIST}


    Set Suite Variable    ${DEVICE_LIST}
    Set Suite Variable    ${DUT}
    Set Suite Variable    ${CE1}    ${test_config["CE1"]}
    Set Suite Variable    ${CE2}    ${test_config["CE2"]}
    Set Suite Variable    ${PE2}    ${test_config["PE2"]}
    Set Suite Variable    ${VRF_IP}
    Set Suite Variable    ${INTERFACE}

    Log To Console    ------------------------------------------------------------
    Log To Console    Configuration Loaded:
    Log To Console    - Protocol: ${CONNECTION_PROTOCOL}
    Log To Console    - DUT IP: ${dut_ip}
    Log To Console    - Device ID: ${DEVICE_ID}
    Log To Console    - Execution ID: ${EXECUTION_ID}
    Log To Console    - Devices Loaded: ${DEVICE_COUNT}
    Log To Console    ------------------------------------------------------------


