*** Settings ***
Library           ../../../resources/keywords/BB-TRF-VRF-002.py
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
BB-TRF-VRF-002 VRF Teardown End-to-End Test
    [Tags]    BB-TRF-VRF-002

    Log     ==== Starting VRF Teardown Test ====

    Run VRF Teardown On BB
    Run VRF Teardown On PE2
    Validate VRF Teardown

    Log     ==== VRF Teardown Test Completed Successfully ====


*** Keywords ***
# ==================================================
# SUITE SETUP
# ==================================================
Initialize Test Environment
    Initialize Custom Log File
    Load Device Info

    Log     ==== Opening Device Connections ====

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


# ==================================================
# SUITE TEARDOWN
# ==================================================
Cleanup Test Environment
    Log     ==== Closing Device Connections ====
    CLOSE ALL DEVICE CONNECTIONS


# ==================================================
# LOAD CONFIG
# ==================================================
Load Device Info
    Log     Loading config from provided variables

    Run Keyword If    """${DEVICE_JSON}""" == ""    Fail    DEVICE_JSON not provided
    Run Keyword If    """${TEST_JSON}""" == ""      Fail    TEST_JSON not provided

    ${device_config}=    Evaluate    json.loads(r'''${DEVICE_JSON}''')    json
    ${test_config}=      Evaluate    json.loads(r'''${TEST_JSON}''')      json

    # ================= BB =================
    ${BB}=           Set Variable    ${device_config["BB"]}
    ${bb_ip}=        Set Variable    ${BB["ip"]}
    ${bb_user}=      Set Variable    ${BB["user"]}
    ${bb_pass}=      Set Variable    ${BB["password"]}
    ${bb_dev_id}=    Set Variable    ${BB.get("device_id", "2001")}
    ${bb_exec_id}=   Set Variable    ${BB.get("execution_id", "1")}
    ${protocol}=     Set Variable    ${BB.get("connection_protocol", "SSH")}

    # ================= PC =================
    ${PC}=           Set Variable    ${test_config["PC"]}
    ${pc_name}=      Set Variable    PC
    ${pc_ip}=        Set Variable    ${PC["ip"]}
    ${pc_user}=      Set Variable    ${PC["user"]}
    ${pc_pass}=      Set Variable    ${PC["password"]}
    ${pc_dev_id}=    Set Variable    ${PC.get("device_id", "2")}
    ${pc_exec_id}=   Set Variable    ${PC.get("execution_id", "1")}
    ${pc_protocol}=  Set Variable    ${PC.get("connection_protocol", "SSH")}

    # ================= DEVICE LIST =================
    ${bb_device}=    Create Dictionary
    ...    name=DUT
    ...    protocol=${protocol}
    ...    ip=${bb_ip}
    ...    user=${bb_user}
    ...    pass=${bb_pass}
    ...    device_id=${bb_dev_id}
    ...    execution_id=${bb_exec_id}

    ${pc_device}=    Create Dictionary
    ...    name=${pc_name}
    ...    protocol=${pc_protocol}
    ...    ip=${pc_ip}
    ...    user=${pc_user}
    ...    pass=${pc_pass}
    ...    device_id=${pc_dev_id}
    ...    execution_id=${pc_exec_id}

    @{DEVICE_LIST}=    Create List    ${bb_device}    ${pc_device}

    Set Suite Variable    @{DEVICE_LIST}
    Set Suite Variable    ${TEST_CFG}    ${test_config}
    Set Suite Variable    ${PC_NAME}     ${pc_name}


Run VRF Teardown On BB
    Log        ==== VRF Teardown on BB (NXP) ====
    Teardown Vrf    DUT    ${TEST_CFG["BB"]}
    Restart Frr     DUT


Run VRF Teardown On PE2
    Log     ==== VRF Teardown on PC (RPi) ====
    Teardown Vrf    ${PC_NAME}    ${TEST_CFG["PC"]}
    Restart Frr     ${PC_NAME}


Validate VRF Teardown
    Log     ==== Validating VRF Teardown ====
    Validate Vrf Removed    DUT
    Validate Vrf Removed    ${PC_NAME}

