*** Settings ***
Library           ../../resources/keywords/NN-006.py
Library           ../../resources/keywords/firewall_mqtt.py
Library           OperatingSystem
Library           JSONLibrary
Library           Collections
Library           String
Library           BuiltIn
Resource          ../../resources/keywords/common_keywords.robot


*** Variables ***
${DEVICE_JSON}          ${EMPTY}


*** Test Cases ***
Firewall Rule Ping Behavior Test
    [Tags]    NN-006

    Load Device Info



*** Keywords ***



Load Device Info
    Log Message To Custom File   📁 Loading config from provided variables    
    Log To Console    ============================================================
    Log To Console    Configuration Loaded:
    Log To Console    - Protocol: ${CONNECTION_PROTOCOL}
 ================================



