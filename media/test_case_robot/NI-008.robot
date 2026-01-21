*** Settings ***
Library           ../../resources/keywords/NI-008.py
Library           ../../resources/keywords/access_control_mqtt.py
Library           JSONLibrary
Library           BuiltIn
Library           Collections
Resource          ../../resources/keywords/common_keywords.robot
Suite Setup       Initialize Test Environment
Suite Teardown    Cleanup Test Environment


*** Variables ***
${DEVICE_JSON}          ${EMPTY}
${TEST_JSON}            ${EMPTY}
${LOG_FOLDER}           ${CURDIR}/../../logs
${CONNECTION_PROTOCOL}  SSH
${DEVICE_ID}            ${EMPTY}
${EXECUTION_ID}         ${EMPTY}


*** Test Cases ***
Verify SSH Access - PC Then BB
    [Tags]    NI-008
    Load Device Info
    Log Message To Custom File   ==== Verifying chained SSH: PC -> BBBBBBB ====

    ${result}=    Run PC-BB Access Test

    Log Message To Custom File   Expected exit_code: 0, Actual: ${result['exit_code']}
    Log Message To Custom File   Output: ${result['stdout']}

    Should Be Equal As Integers    ${result['exit_code']}    0    SSH Access Test Failed
    Should Contain    ${result['stdout']}    Connected

    Log Message To Custom File   ✅ SSH PC → BB Access Success


*** Keywords ***

Initialize Test Environment
    [Documentation]    Setup logging and load configuration
    Initialize Custom Log File
    Load Device Info

    Run Keyword If    '${CONNECTION_PROTOCOL}' == 'MQTT'
    ...    MQTT Initialize Connection    ${DEVICE_ID}    ${EXECUTION_ID}
    ...    ELSE
    ...    Log To Console    Using SSH protocol (no initialization needed)


Cleanup Test Environment
    [Documentation]    Cleanup after test
    Run Keyword If    '${CONNECTION_PROTOCOL}' == 'MQTT'
    ...    MQTT Close Connection


Load Device Info
    [Documentation]    Parse JSON configs and set global variables
    Log Message To Custom File   📁 Loading config from provided variables

    ${device_config}=    Evaluate    json.loads(r'''${DEVICE_JSON}''')    json
    ${test_config}=      Evaluate    json.loads(r'''${TEST_JSON}''')      json

    # BB / Target Device
    ${BB}=          Set Variable    ${device_config["BB"]}
    ${bb_ip}=       Set Variable    ${BB["ip"]}
    ${bb_user}=     Set Variable    ${BB["user"]}
    ${bb_pass}=     Set Variable    ${BB["password"]}
    ${protocol}=    Set Variable    ${BB.get("connection_protocol", "SSH")}

    # PC / Test Machine
    ${PC}=          Set Variable    ${test_config["PC"]}
    ${pc_ip}=       Set Variable    ${PC["ip"]}
    ${pc_user}=     Set Variable    ${PC["user"]}
    ${pc_pass}=     Set Variable    ${PC["password"]}

    # MQTT extras
    ${dev_id}=      Set Variable    ${BB.get("device_id", "1001")}
    ${exec_id}=     Set Variable    ${BB.get("execution_id", "1")}

    # Export to Suite
    Set Suite Variable    ${bb_ip}
    Set Suite Variable    ${bb_user}
    Set Suite Variable    ${bb_pass}
    Set Suite Variable    ${pc_ip}
    Set Suite Variable    ${pc_user}
    Set Suite Variable    ${pc_pass}
    Set Suite Variable    ${CONNECTION_PROTOCOL}    ${protocol}
    Set Suite Variable    ${DEVICE_ID}              ${dev_id}
    Set Suite Variable    ${EXECUTION_ID}           ${exec_id}

    Log To Console    ------------------------------------------------------------
    Log To Console    Configuration Loaded:
    Log To Console    - Protocol: ${CONNECTION_PROTOCOL}
    Log To Console    - BB IP: ${bb_ip}
    Log To Console    - Device ID: ${DEVICE_ID}
    Log To Console    - Execution ID: ${EXECUTION_ID}
    Log To Console    ------------------------------------------------------------


Run PC-BB Access Test
    [Documentation]    Use SSH or MQTT method to test access PC -> BB
    Log To Console               ==== Running PC → BB SSH Access Test ====
    Log Message To Custom File   ==== Running PC → BB SSH Access Test ====

    ${result}=    Run Keyword If    '${CONNECTION_PROTOCOL}' == 'SSH'
    ...    SSH PC Then BB    ${pc_ip}    ${pc_user}    ${pc_pass}    ${bb_ip}    ${bb_user}    ${bb_pass}
    ...    ELSE IF    '${CONNECTION_PROTOCOL}' == 'MQTT'
    ...    MQTT SSH PC Then BB    ${pc_ip}    ${pc_user}    ${pc_pass}    ${bb_ip}    ${bb_user}    ${bb_pass}

    RETURN    ${result}
