*** Settings ***
Library           ../../resources/keywords/BB-FF-0011.py
Library           ../../resources/keywords/firewall_mqtt.py
Library           OperatingSystem
Library           JSONLibrary
Library           Collections
Library           String
Library           BuiltIn
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
Firewall Rule Ping Behavior Test
    [Tags]    BB-FF-0011

    Load Device Info



*** Keywords ***
Setup All Test Devices
    SSH All Devices
    ...    name=BB    ip=10.10.10.23    username=root    password=root
    ...    name=RPI1  ip=10.10.10.24    username=root    password=root


Initialize Test Environment
    Initialize Custom Log File
    Load Device Info
    
    Run Keyword If    '${CONNECTION_PROTOCOL}' == 'MQTT'
    ...    MQTT Initialize Connection    ${DEVICE_ID}    ${EXECUTION_ID}
    ...    ELSE
    ...    Log To Console    Using SSH connection (no initialization needed)

Cleanup Test Environment
    Run Keyword If    '${CONNECTION_PROTOCOL}' == 'MQTT'
    ...    MQTT Close Connection


Load Device Info
    Log Message To Custom File   📁 Loading config from provided variables
    
    ${device_config}=    Evaluate    json.loads("""${DEVICE_JSON}""")    json
    ${test_config}=      Evaluate    json.loads("""${TEST_JSON}""")      json

    ${BB}=    Set Variable    ${device_config["BB"]}
    ${ow_ip}=         Set Variable    ${BB["ip"]}
    ${ow_user}=       Set Variable    ${BB["user"]}
    ${ow_pass}=       Set Variable    ${BB["password"]}
    ${protocol}=      Set Variable    ${BB.get("connection_protocol", "SSH")}

    ${PC}=    Set Variable    ${test_config["PC"]}
    ${rpi_ip}=        Set Variable    ${PC["ip"]}
    ${rpi_user}=      Set Variable    ${PC["user"]}
    ${rpi_pass}=      Set Variable    ${PC["password"]}
    ${ping_ip}=       Set Variable    ${PC["ping_ip"]}

    ${dev_id}=        Set Variable    ${BB.get("device_id", "1001")}
    ${exec_id}=       Set Variable    ${BB.get("execution_id", "1")}

    Set Suite Variable    ${ow_ip}
    Set Suite Variable    ${ow_user}
    Set Suite Variable    ${ow_pass}
    Set Suite Variable    ${rpi_ip}
    Set Suite Variable    ${rpi_user}
    Set Suite Variable    ${rpi_pass}
    Set Suite Variable    ${ping_ip}
    Set Suite Variable    ${CONNECTION_PROTOCOL}    ${protocol}
    Set Suite Variable    ${DEVICE_ID}              ${dev_id}
    Set Suite Variable    ${EXECUTION_ID}           ${exec_id}
    
    Run Keyword If    '${CONNECTION_PROTOCOL}' == 'SSH'
    ...    Set Ping Ip    ${ping_ip}
    ...    ELSE IF    '${CONNECTION_PROTOCOL}' == 'MQTT'
    ...    MQTT Set Ping Ip    ${ping_ip}
    
    Log To Console    ============================================================
    Log To Console    Configuration Loaded:
    Log To Console    - Protocol: ${CONNECTION_PROTOCOL}
    Log To Console    - OpenWrt IP: ${ow_ip}
    Log To Console    - Device ID: ${DEVICE_ID}
    Log To Console    - Execution ID: ${EXECUTION_ID}
    Log To Console    - Ping Target: ${ping_ip}
    Log To Console    ============================================================


