*** Settings ***
Library           ../../../resources/keywords/BB-TRF-4G5G-001.py
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
BB-TRF-4G5G-001 ETH LAN → 4G/5G WAN Traffic Test
    [Documentation]    Verify LAN client traffic via 4G/5G WAN with metrics
    [Tags]    BB-TRF-4G5G-001

    Log Message To Custom File    ==== Starting ETH LAN → 4G/5G WAN Test ====

    Log Message To Custom File    ==== Ensuring Modem & WAN Connectivity ====

    ${modem_ip}=    Ensure Modem Connected        DUT    ${dut_interface}
    Set Suite Variable    ${modem_ip}
    Ensure WWAN Default Route     DUT    ${dut_interface}   ${modem_ip}
    Check RPi Routing Dynamic     ${pc_name}    ${pc_interface}

    Log Message To Custom File    ==== Starting Traffic & System Metrics ====

    Monitor System Stats Around Iperf    ${dut_device}    ${metrics_interval}
    Ping All RPis         ${pc_name}    ${pc_interface}    ${remote_ping_ip}    ${idle_ping_duration}

    Log Message To Custom File    ==== Stopping Metrics & Cleaning Routes ====

    Wait For Monitoring To Finish
    Cleanup WWAN Default Route    DUT    ${dut_interface}    ${modem_ip}
   
    Log Message To Custom File    ==== ETH LAN → 4G/5G WAN Test Completed Successfully ====
 
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
 
    # ================= DUT / BB =================
    ${DUT}=            Set Variable    ${device_config["BB"]}
    ${dut_ip}=         Set Variable    ${DUT["ip"]}
    ${dut_user}=       Set Variable    ${DUT["user"]}
    ${dut_pass}=       Set Variable    ${DUT["password"]}
    ${dut_dev_id}=     Set Variable    ${DUT.get("device_id", "2001")}
    ${dut_exec_id}=    Set Variable    ${DUT.get("execution_id", "1")}
    ${protocol}=       Set Variable    ${DUT.get("connection_protocol", "SSH")}
 
    # ================= PC / LAN CLIENT =================
    ${PC}=             Set Variable    ${test_config["PC"]}
    ${pc_name}=        Set Variable    ${PC["name"]}
    ${pc_ip}=          Set Variable    ${PC["ip"]}
    ${pc_user}=        Set Variable    ${PC["user"]}
    ${pc_pass}=        Set Variable    ${PC["password"]}
    ${pc_dev_id}=      Set Variable    ${PC.get("device_id", "2002")}
    ${pc_exec_id}=     Set Variable    ${PC.get("execution_id", "1")}
    ${pc_protocol}=    Set Variable    ${PC.get("connection_protocol", "SSH")}
 
    # ================= TEST PARAMETERS =================
    ${pc_interface}=             Set Variable    ${test_config["pc_interface"]}
    ${dut_interface}=            Set Variable    ${test_config["dut_interface"]}
    ${remote_ping_ip}=           Set Variable    ${test_config["remote_ping_ip"]}
    ${idle_ping_duration}=       Set Variable    ${test_config["idle_ping_duration"]}
    ${test_duration}=            Set Variable    ${test_config["test_duration"]}
    ${metrics_interval}=         Set Variable    ${test_config["metrics_interval"]}
 
    # ================= DEVICE LIST =================
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
 
    # ================= EXPORT VARIABLES =================
    Set Suite Variable    ${DEVICE_LIST}
    Set Suite Variable    ${DEVICE_COUNT}
    Set Suite Variable    ${dut_device}
    Set Suite Variable    ${pc_name}
    Set Suite Variable    ${pc_interface}
    Set Suite Variable    ${dut_interface}
    Set Suite Variable    ${remote_ping_ip}
    Set Suite Variable    ${idle_ping_duration}
    Set Suite Variable    ${test_duration}
    Set Suite Variable    ${metrics_interval}
    Set Suite Variable    ${CONNECTION_PROTOCOL}    ${protocol}
    Set Suite Variable    ${DEVICE_ID}              ${dut_dev_id}
    Set Suite Variable    ${EXECUTION_ID}           ${dut_exec_id}
 
    Log To Console    ------------------------------------------------------------
    Log To Console    Configuration Loaded:
    Log To Console    - Protocol: ${CONNECTION_PROTOCOL}
    Log To Console    - DUT IP: ${dut_ip}
    Log To Console    - Device ID: ${DEVICE_ID}
    Log To Console    - Execution ID: ${EXECUTION_ID}
    Log To Console    - Devices Loaded: ${DEVICE_COUNT}
    Log To Console    ------------------------------------------------------------

 


Capture Ifconfig Errors
    Log Message To Custom File   === capturing ifconfig snapshot errors ===

    Capture Ifconfig Snapshot For Devices    ${dut_device}   ${dut_interface}
    Validate Ifconfig Errors For Devices     ${dut_device}   ${dut_interface}