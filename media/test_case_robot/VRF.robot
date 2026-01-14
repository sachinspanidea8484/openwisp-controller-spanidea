*** Settings ***
Library           ../../resources/keywords/VRF.py
Library           ../../resources/keywords/VRF-mqtt.py
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
 
VRF End-to-End Automation
 
    [Tags]    BB-TRF-VRF-001

    Load Device Info
 
    Fetch FRR Configs
 
    Check And Establish VRF
 
    Verify VRF Establishment
 
    Test Ping Connectivity


*** Keywords ***
 
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

    # --- BB Device ---

    ${BB}=           Set Variable    ${device_config["BB"]}

    ${BB_ip}=        Set Variable    ${BB.get("ip","")}

    ${BB_user}=      Set Variable    ${BB.get("user","")}

    ${BB_password}=  Set Variable    ${BB.get("password","")}

    # Pull from TEST_JSON (correct keys)

    ${BB_interface}=    Set Variable    ${test_config["BB"]["interface"]}

    ${BB_vrf_ip}=       Set Variable    ${test_config["BB"]["vrf_ip"]}

    # Merge into dict so Python can use

    Set To Dictionary    ${BB}    interface=${BB_interface}

    Set To Dictionary    ${BB}    vrf_ip=${BB_vrf_ip}

    # --- Other devices ---

    ${PE2}=   Set Variable    ${test_config.get("PE2",{})}

    ${CE1}=   Set Variable    ${test_config.get("CE1",{})}

    ${CE2}=   Set Variable    ${test_config.get("CE2",{})}

    # --- Protocol & IDs ---

    ${CONNECTION_PROTOCOL}=    Set Variable    ${BB.get("connection_protocol","SSH")}

    ${DEVICE_ID}=              Set Variable    ${BB.get("device_id","1001")}

    ${EXECUTION_ID}=           Set Variable    ${BB.get("execution_id","1")}

    # --- Set Suite Variables ---

    Set Suite Variable    ${BB}

    Set Suite Variable    ${BB_ip}

    Set Suite Variable    ${BB_user}

    Set Suite Variable    ${BB_password}

    Set Suite Variable    ${BB_interface}

    Set Suite Variable    ${BB_vrf_ip}

    Set Suite Variable    ${PE2}

    Set Suite Variable    ${CE1}

    Set Suite Variable    ${CE2}

    Set Suite Variable    ${CONNECTION_PROTOCOL}

    Set Suite Variable    ${DEVICE_ID}

    Set Suite Variable    ${EXECUTION_ID}

    Log To Console    ============================================================

    Log To Console    Configuration Loaded:

    Log To Console    - Protocol: ${CONNECTION_PROTOCOL}

    Log To Console    - BB IP: ${BB_ip}

    Log To Console    - BB Interface: ${BB_interface}

    Log To Console    - BB VRF IP: ${BB_vrf_ip}

    Log To Console    ============================================================

Fetch FRR Configs
 
    Log To Console               ==== Fetching FRR Configs from all devices ====
 
    Log Message To Custom File   ==== Fetching FRR Configs from all devices ====
 
    Run Keyword If    '${CONNECTION_PROTOCOL}' == 'SSH'
 
    ...    Get Frr Config    ${CE1}
 
    ...    ELSE IF    '${CONNECTION_PROTOCOL}' == 'MQTT'
 
    ...    MQTT Get Frr Config    ${CE1}
 
    Run Keyword If    '${CONNECTION_PROTOCOL}' == 'SSH'
 
    ...    Get Frr Config    ${CE2}
 
    ...    ELSE IF    '${CONNECTION_PROTOCOL}' == 'MQTT'
 
    ...    MQTT Get Frr Config    ${CE2}
 
    Run Keyword If    '${CONNECTION_PROTOCOL}' == 'SSH'
 
    ...    Get Frr Config    ${BB}
 
    ...    ELSE IF    '${CONNECTION_PROTOCOL}' == 'MQTT'
 
    ...    MQTT Get Frr Config    ${BB}
 
    Run Keyword If    '${CONNECTION_PROTOCOL}' == 'SSH'
 
    ...    Get Frr Config    ${PE2}
 
    ...    ELSE IF    '${CONNECTION_PROTOCOL}' == 'MQTT'
 
    ...    MQTT Get Frr Config    ${PE2}


Check And Establish VRF
 
    Log To Console               ==== Checking VRF Status ====
 
    Log Message To Custom File   ==== Checking VRF Status ====
 
    ${st1}=    Run Keyword If    '${CONNECTION_PROTOCOL}' == 'SSH'
 
    ...    Check Vrf Established    ${BB}
 
    ...    ELSE    MQTT Check Vrf Established    ${BB}

    ${st2}=    Run Keyword If    '${CONNECTION_PROTOCOL}' == 'SSH'
 
    ...    Check Vrf Established    ${PE2}
 
    ...    ELSE    MQTT Check Vrf Established    ${PE2}

    Run Keyword If    ${st1} and ${st2}
 
    ...    Log To Console    VRF Already Established
 
    ...    ELSE    Establish VRF On Devices


Establish VRF On Devices
 
    Log To Console               ==== VRF not established - Creating VRF ====
 
    Log Message To Custom File   ==== VRF not established - Creating VRF ====
 
    Run Keyword If    '${CONNECTION_PROTOCOL}' == 'SSH'
 
    ...    Create Vrf    ${BB}
 
    ...    ELSE IF    '${CONNECTION_PROTOCOL}' == 'MQTT'
 
    ...    MQTT Create Vrf    ${BB}
 
    Run Keyword If    '${CONNECTION_PROTOCOL}' == 'SSH'
 
    ...    Create Vrf    ${PE2}
 
    ...    ELSE IF    '${CONNECTION_PROTOCOL}' == 'MQTT'
 
    ...    MQTT Create Vrf    ${PE2}

    Log To Console               ==== Restarting FRR ====
 
    Log Message To Custom File   ==== Restarting FRR ====
 
    Run Keyword If    '${CONNECTION_PROTOCOL}' == 'SSH'
 
    ...    Restart Frr    ${BB}
 
    ...    ELSE IF    '${CONNECTION_PROTOCOL}' == 'MQTT'
 
    ...    MQTT Restart Frr    ${BB}
 
    Run Keyword If    '${CONNECTION_PROTOCOL}' == 'SSH'
 
    ...    Restart Frr    ${PE2}
 
    ...    ELSE IF    '${CONNECTION_PROTOCOL}' == 'MQTT'
 
    ...    MQTT Restart Frr    ${PE2}


Verify VRF Establishment
 
    Log To Console               ==== Verifying VRF Establishment ====
 
    Log Message To Custom File   ==== Verifying VRF Establishment ====
 
    Run Keyword If    '${CONNECTION_PROTOCOL}' == 'SSH'
 
    ...    Wait Until Keyword Succeeds    10 times    5s    Check Vrf Established    ${BB}
 
    ...    ELSE IF    '${CONNECTION_PROTOCOL}' == 'MQTT'
 
    ...    Wait Until Keyword Succeeds    10 times    5s    MQTT Check Vrf Established    ${BB}
 
    Run Keyword If    '${CONNECTION_PROTOCOL}' == 'SSH'
 
    ...    Wait Until Keyword Succeeds    10 times    5s    Check Vrf Established    ${PE2}
 
    ...    ELSE IF    '${CONNECTION_PROTOCOL}' == 'MQTT'
 
    ...    Wait Until Keyword Succeeds    10 times    5s    MQTT Check Vrf Established    ${PE2}

    Log To Console    VRF Successfully Established


Test Ping Connectivity
 
    Log To Console               ==== Testing Ping Connectivity ====
 
    Log Message To Custom File   ==== Testing Ping Connectivity ====
 
    ${p1}=    Run Keyword If    '${CONNECTION_PROTOCOL}' == 'SSH'
 
    ...    Ping Test    ${CE1}    ${CE1["ping_target"]}
 
    ...    ELSE    MQTT Ping Test    ${CE1}    ${CE1["ping_target"]}

    ${p2}=    Run Keyword If    '${CONNECTION_PROTOCOL}' == 'SSH'
 
    ...    Ping Test    ${CE2}    ${CE2["ping_target"]}
 
    ...    ELSE    MQTT Ping Test    ${CE2}    ${CE2["ping_target"]}

    Should Be True    ${p1}
 
    Should Be True    ${p2}
 
    Log To Console    ==== VRF Test Completed Successfully ====

 
