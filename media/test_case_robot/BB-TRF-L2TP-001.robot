*** Settings ***
Library           ../../../resources/keywords/BB-TRF-L2TP-001.py
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
BB-TRF-L2TP-001 L2TP Tunnel End-to-End Test
    [Tags]    BB-TRF-L2TP-001

    Load Device Info
    Log Message To Custom File   ==== Starting L2TP Tunnel Test ====
  
    Run L2TP Setup On DUT
    Run L2TP Setup On RPI
    Run L2TP Verification On DUT
    # Run L2TP Verification On RPI
    Run L2TP Teardown
   
    Log Message To Custom File    L2TP Tunnel End-to-End Test Successful


*** Keywords ***
# =============SUITE SETUP=====================
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


# ===============SUITE TEARDOWN==================
Cleanup Test Environment
    Log To Console    ==== Closing Device Connections ====
    CLOSE ALL DEVICE CONNECTIONS   


# ================LOAD CONFIG====================
Load Device Info
    Log Message To Custom File    Loading config from provided variables

    Run Keyword If    '${DEVICE_JSON}' == '' or '${TEST_JSON}' == ''
    ...    Fail    Device or Test JSON not provided

    ${device_config}=    Evaluate    json.loads(r'''${DEVICE_JSON}''')    json
    ${test_config}=      Evaluate    json.loads(r'''${TEST_JSON}''')      json

    # BB / DEVICE UNDER TEST [DUT]
    ${DUT}=          Set Variable    ${device_config["BB"]}
    # ${dut_name}=     Set Variable    ${DUT["name"]}
    ${dut_ip}=       Set Variable    ${DUT["ip"]}
    ${dut_user}=     Set Variable    ${DUT["user"]}
    ${dut_pass}=     Set Variable    ${DUT["password"]}
    ${dut_dev_id}=   Set Variable    ${DUT.get("device_id", "2001")}
    ${dut_exec_id}=  Set Variable    ${DUT.get("execution_id", "1")}
    ${protocol}=     Set Variable    ${DUT.get("connection_protocol", "SSH")}

    # RPI / PC/ HELPER DEVICE
    ${PC}=           Set Variable    ${test_config["PC"]}
    ${pc_name}=      Set Variable    ${PC["name"]}
    ${pc_ip}=        Set Variable    ${PC["ip"]}
    ${pc_user}=      Set Variable    ${PC["user"]}
    ${pc_pass}=      Set Variable    ${PC["password"]}
    ${pc_dev_id}=    Set Variable    ${PC.get("device_id", "2001")}
    ${pc_exec_id}=   Set Variable    ${PC.get("execution_id", "1")}
    ${pc_protocol}=  Set Variable    ${PC.get("connection_protocol", "SSH")}

    # L2TP Parameter
    ${BB_L2TP}=     Set Variable    ${test_config["BB_L2TP"]}
    ${RPI_L2TP}=     Set Variable    ${test_config["RPI_L2TP"]}

 
    # DEVICE LIST (KEY CHANGE)
    ${dut_device}=    Create Dictionary
    ...    name=DUT
    ...    protocol=${protocol}
    ...    ip=${dut_ip}
    ...    user=${dut_user}
    ...    pass=${dut_pass}
    ...    device_id=${dut_dev_id}
    ...    execution_id=${dut_exec_id}

    ${pc_device}=   Create Dictionary 
    ...    name=${pc_name}
    ...    protocol=${protocol}
    ...    ip=${pc_ip}
    ...    user=${pc_user}
    ...    pass=${pc_pass}
    ...    device_id=${pc_dev_id}
    ...    execution_id=${pc_exec_id}
    

    @{DEVICE_LIST}=    Create List    ${dut_device}    ${pc_device}   
    ${DEVICE_COUNT}=    Get Length    ${DEVICE_LIST}

    # Export to Suite
    Set Suite Variable    ${DEVICE_LIST}
    Set Suite Variable    ${dut_ip}
    Set Suite Variable    ${dut_user}
    Set Suite Variable    ${dut_pass}
    # Set Suite Variable    ${dut_name}
    Set Suite Variable    ${CONNECTION_PROTOCOL}    ${protocol}
    Set Suite Variable    ${DEVICE_ID}              ${dut_dev_id}
    Set Suite Variable    ${EXECUTION_ID}           ${dut_exec_id}
    Set Suite Variable    ${pc_ip}
    Set Suite Variable    ${pc_user}
    Set Suite Variable    ${pc_pass}
    Set Suite Variable    ${pc_name}
    Set Suite Variable    ${BB_L2TP}
    Set Suite Variable    ${RPI_L2TP}

    Log To Console    ------------------------------------------------------------
    Log To Console    Configuration Loaded:
    Log To Console    - Protocol: ${CONNECTION_PROTOCOL}
    Log To Console    - DUT IP: ${dut_ip}
    Log To Console    - Device ID: ${DEVICE_ID}
    Log To Console    - Execution ID: ${EXECUTION_ID}
    Log To Console    - Devices Loaded: ${DEVICE_COUNT}
    Log To Console    ------------------------------------------------------------


# ==========================================================
# WRAPPER KEYWORDS FOR L2TP (SSH or MQTT)
# ==========================================================
Run L2TP Setup On DUT
    Log To Console    ==== Running L2TP Setup on ${dut_ip} ====

    SET UP L2TP TUNNEL ON DUT
    ...    DUT
    ...    ${BB_L2TP["local_ip"]}    ${BB_L2TP["remote_ip"]}    ${BB_L2TP["tunnel_id"]}    ${BB_L2TP["session_id"]}
    ...    ${BB_L2TP["peer_tunnel_id"]}   ${BB_L2TP["peer_session_id"]}     ${BB_L2TP["overlay_ip"]}    ${BB_L2TP["udp_port"]}    
       

Run L2TP Setup On RPI
    Log To Console    ==== Running L2TP Setup on ${pc_ip}  ====

    SET UP L2TP TUNNEL ON RPI
    ...    ${pc_name}    ${pc_pass}     
    ...    ${RPI_L2TP["local_ip"]}    ${RPI_L2TP["remote_ip"]}    ${RPI_L2TP["tunnel_id"]}    ${RPI_L2TP["session_id"]}    
    ...    ${RPI_L2TP["peer_tunnel_id"]}   ${RPI_L2TP["peer_session_id"]}     ${RPI_L2TP["overlay_ip"]}    ${RPI_L2TP["udp_port"]} 

     

Run L2TP Verification On DUT
    [Documentation]    Verify L2TP tunnels on DUT
    Log To Console    ==== Running L2TP Verification on ${dut_ip} ====

    VERIFY L2TP TUNNEL
    ...    ${CONNECTION_PROTOCOL}    DUT    ${dut_pass}
    ...    ${pc_name}   
    ...    ${BB_L2TP["underlay_iface"]}    ${BB_L2TP["local_ip"]}    ${BB_L2TP["remote_ip"]} 
    ...    ${BB_L2TP["overlay_ip"]}    ${RPI_L2TP["overlay_ip"]}    ${BB_L2TP["udp_port"]}



Run L2TP Verification On RPI
    [Documentation]    Verify L2TP tunnels on RPI
    Log To Console    ==== Running L2TP Verification on RPI ====

    VERIFY L2TP TUNNEL 
    ...    ${CONNECTION_PROTOCOL}    ${pc_name}    ${pc_pass}
    ...    DUT
    ...    ${RPI_L2TP["underlay_iface"]}    ${RPI_L2TP["local_ip"]}    ${RPI_L2TP["remote_ip"]}    
    ...    ${RPI_L2TP["overlay_ip"]}    ${BB_L2TP["overlay_ip"]}    ${RPI_L2TP["udp_port"]}
  

Run L2TP Teardown
    [Documentation]    Start teardown L2TP tunnels
    Log Message To Custom File    --- Teardown L2TP tunnels on (${dut_ip}) and (${pc_ip}) ---

    TEARDOWN L2TP TUNNEL
    ...    DUT    
    ...    ${dut_pass}    
    ...    ${BB_L2TP["tunnel_id"]}    
    ...    ${BB_L2TP["session_id"]}

    TEARDOWN L2TP TUNNEL
    ...    ${pc_name}    
    ...    ${pc_pass}    
    ...    ${RPI_L2TP["tunnel_id"]}    
    ...    ${RPI_L2TP["session_id"]}







