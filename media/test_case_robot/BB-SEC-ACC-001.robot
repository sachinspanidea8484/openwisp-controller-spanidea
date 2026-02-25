*** Settings ***
Library           ../../../resources/keywords/BB-SEC-ACC-001.py
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
BB-SEC-ACC-001 Verify PC Can SSH To BB
    [Documentation]    Verify PC can SSH into BB device
    [Tags]    BB-SEC-ACC-001
    Log Message To Custom File    ==== Starting SSH Access Control Test ====
    RUN Verify SSH Access
    Log Message To Custom File    ==== SSH Access Control Test Completed Successfully ====


*** Keywords ***
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


Cleanup Test Environment
    Log To Console    ==== Closing Device Connections ====
    CLOSE ALL DEVICE CONNECTIONS


Load Device Info
    Log Message To Custom File    Loading configuration from JSON variables

    Run Keyword If    '${DEVICE_JSON}' == '' or '${TEST_JSON}' == ''
    ...    Fail    DEVICE_JSON or TEST_JSON not provided

    ${device_config}=    Evaluate    json.loads(r'''${DEVICE_JSON}''')    json
    ${test_config}=      Evaluate    json.loads(r'''${TEST_JSON}''')      json

    ${DUT}=            Set Variable    ${device_config["BB"]}
    ${dut_ip}=         Set Variable    ${DUT["ip"]}
    ${dut_user}=       Set Variable    ${DUT["user"]}
    ${dut_pass}=       Set Variable    ${DUT["password"]}
    ${dut_dev_id}=     Set Variable    ${DUT.get("device_id", "2001")}
    ${dut_exec_id}=    Set Variable    ${DUT.get("execution_id", "1")}
    ${protocol}=       Set Variable    ${DUT.get("connection_protocol", "SSH")}

    ${PC}=             Set Variable    ${test_config["PC"]}
    ${pc_name}=        Set Variable    ${PC["name"]}
    ${pc_ip}=          Set Variable    ${PC["ip"]}
    ${pc_user}=        Set Variable    ${PC["user"]}
    ${pc_pass}=        Set Variable    ${PC["password"]}
    ${pc_dev_id}=      Set Variable    ${PC.get("device_id", "2002")}
    ${pc_exec_id}=     Set Variable    ${PC.get("execution_id", "1")}
    ${pc_protocol}=    Set Variable    ${PC.get("connection_protocol", "SSH")}

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

    Set Suite Variable    ${DEVICE_LIST}
    Set Suite Variable    ${DEVICE_COUNT}
    Set Suite Variable    ${DUT_NAME}            DUT
    Set Suite Variable    ${pc_name}
    Set Suite Variable    ${dut_ip}
    Set Suite Variable    ${dut_user}
    Set Suite Variable    ${dut_pass}
    Set Suite Variable    ${CONNECTION_PROTOCOL}    ${protocol}
    Set Suite Variable    ${DEVICE_ID}              ${dut_dev_id}
    Set Suite Variable    ${EXECUTION_ID}           ${dut_exec_id}

    Log To Console    ------------------------------------------------------------
    Log To Console    Configuration Loaded:
    Log To Console    - Protocol: ${CONNECTION_PROTOCOL}
    Log To Console    - DUT IP: ${dut_ip}
    Log To Console    - PC IP: ${pc_ip}
    Log To Console    - Device ID: ${DEVICE_ID}
    Log To Console    - Execution ID: ${EXECUTION_ID}
    Log To Console    - Devices Loaded: ${DEVICE_COUNT}
    Log To Console    ------------------------------------------------------------


RUN Verify SSH Access
    VERIFY SSH ACCESS PC TO BB
    ...    ${pc_name}
    ...    ${dut_ip}
    ...    ${dut_user}
    ...    ${dut_pass}

