
*** Settings ***
Library           ../../../resources/keywords/BB-TRF-L2TP-002.py
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
BB-TRF-L2TP-002 L2TP Tunnel Redundancy End-to-End Test
    [Tags]    BB-TRF-L2TP-002

    # Load Device Info
    Log Message To Custom File   ==== Starting L2TP Tunnel Redundancy Test ====
   
    Run L2TP Setup On DUT
    Run L2TP Setup On PC
    RUN CONFIGURE ROUTING SETUP ON DUT
    RUN CONFIGURE ROUTING SETUP ON PC
    Run L2TP Redundancy Verification On DUT
    Run L2TP Teardown
   
    Log Message To Custom File    L2TP Tunnel Redundancy End-to-End Test Successful


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
   
  
    # DEVICE LIST (KEY CHANGE)
    ${dut_device}=    Create Dictionary
    ...    name=NOKIA
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

    # L2TP Parameter Lists
    ${L2TP_DUT_LIST}=     Set Variable    ${test_config["L2TP_DUT"]}
    ${L2TP_PC_LIST}=      Set Variable    ${test_config["L2TP_PC"]}

    # L2TP Tunnel IPs
    ${dut_lo_ip}=       Set Variable    ${test_config["dut_lo_ip"]}
    ${pc_lo_ip}=       Set Variable    ${test_config["pc_lo_ip"]}


    # Export to Suite
    Set Suite Variable    ${DEVICE_LIST}
    Set Suite Variable    ${dut_ip}
    Set Suite Variable    ${dut_user}
    Set Suite Variable    ${dut_pass}
    Set Suite Variable    ${CONNECTION_PROTOCOL}    ${protocol}
    Set Suite Variable    ${DEVICE_ID}              ${dut_dev_id}
    Set Suite Variable    ${EXECUTION_ID}           ${dut_exec_id}
    Set Suite Variable    ${pc_ip}
    Set Suite Variable    ${pc_user}
    Set Suite Variable    ${pc_pass}
    Set Suite Variable    ${pc_name}
    Set Suite Variable    ${L2TP_DUT_LIST}
    Set Suite Variable    ${L2TP_PC_LIST}
    Set Suite Variable    ${dut_lo_ip}
    Set Suite Variable    ${pc_lo_ip}
 
   
    Log To Console    ------------------------------------------------------------
    Log To Console    Configuration Loaded:
    Log To Console    - Protocol: ${CONNECTION_PROTOCOL}
    Log To Console    - DUT IP: ${dut_ip}
    Log To Console    - Device ID: ${DEVICE_ID}
    Log To Console    - Execution ID: ${EXECUTION_ID}
    Log To Console    - Devices Loaded: ${DEVICE_COUNT}
    Log To Console    ------------------------------------------------------------


# ==========================================================
# WRAPPER KEYWORDS FOR L2TP REDUNDANCY (SSH or MQTT)
# ==========================================================


Run L2TP Setup On DUT
    [Documentation]    Creating L2TP tunnel on DUT
    Log To Console    ==== Running L2TP Setup On DUT ====

        # Get L2TP tunnel list
        FOR    ${tunnel}    IN    @{L2TP_DUT_LIST}
            ${underlay_iface}=    Set Variable    ${tunnel["underlay_iface"]}
            ${local_ip}=          Set Variable    ${tunnel["local_ip"]}
            ${remote_ip}=         Set Variable    ${tunnel["remote_ip"]}
            ${tunnel_id}=         Set Variable    ${tunnel["tunnel_id"]}
            ${session_id}=        Set Variable    ${tunnel["session_id"]}
            ${peer_tunnel_id}=    Set Variable    ${tunnel["peer_tunnel_id"]}
            ${peer_session_id}=   Set Variable    ${tunnel["peer_session_id"]}
            ${overlay_ip}=        Set Variable    ${tunnel["overlay_ip"]}
            ${udp_sport}=         Set Variable    ${tunnel["udp_sport"]}
            ${udp_dport}=         Set Variable    ${tunnel["udp_dport"]}

            SET UP L2TP TUNNEL ON DUT
            ...    NOKIA 
            ...    ${underlay_iface}
            ...    ${local_ip}    
            ...    ${remote_ip}    
            ...    ${tunnel_id}
            ...    ${session_id}
            ...    ${peer_tunnel_id} 
            ...    ${peer_session_id} 
            ...    ${overlay_ip}   
            ...    ${udp_sport}
            ...    ${udp_dport} 
            ...    ${dut_lo_ip} 
        END



Run L2TP Setup On PC
    [Documentation]    Creating L2TP tunnel on PC
    Log To Console    ==== Running L2TP Setup On PC ====

        # Get L2TP tunnel list
        FOR    ${tunnel}    IN    @{L2TP_PC_LIST}
            ${underlay_iface}=    Set Variable    ${tunnel["underlay_iface"]}
            ${local_ip}=          Set Variable    ${tunnel["local_ip"]}
            ${remote_ip}=         Set Variable    ${tunnel["remote_ip"]}
            ${tunnel_id}=         Set Variable    ${tunnel["tunnel_id"]}
            ${session_id}=        Set Variable    ${tunnel["session_id"]}
            ${peer_tunnel_id}=    Set Variable    ${tunnel["peer_tunnel_id"]}
            ${peer_session_id}=   Set Variable    ${tunnel["peer_session_id"]}
            ${overlay_ip}=        Set Variable    ${tunnel["overlay_ip"]}
            ${udp_sport}=         Set Variable    ${tunnel["udp_sport"]}
            ${udp_dport}=         Set Variable    ${tunnel["udp_dport"]}

            SET UP L2TP TUNNEL ON PC
            ...    ${pc_name} 
            ...    ${pc_pass}
            ...    ${underlay_iface}
            ...    ${local_ip}    
            ...    ${remote_ip}    
            ...    ${tunnel_id}
            ...    ${session_id}
            ...    ${peer_tunnel_id} 
            ...    ${peer_session_id} 
            ...    ${overlay_ip}   
            ...    ${udp_sport}
            ...    ${udp_dport} 
            ...    ${pc_lo_ip} 
        END


RUN CONFIGURE ROUTING SETUP ON DUT
    [Documentation]    Setting Primary and Backup route on DUT
    Log To Console    ==== Setting Primary + Backup Route On DUT ====

        CONFIGURE ROUTING SETUP ON DUT
        ...    NOKIA
        ...    ${pc_lo_ip}    
     
RUN CONFIGURE ROUTING SETUP ON PC
    [Documentation]    Setting Primary and Backup route on PC
    Log To Console    ==== Setting Primary + Backup Route On PC ====

        CONFIGURE ROUTING SETUP ON PC
        ...    ${pc_name}
        ...    ${pc_pass}
        ...    ${dut_lo_ip}   



Run L2TP Redundancy Verification On DUT
    [Documentation]    Verify L2TP  tunnels and Redundancy On DUT
    Log To Console    ==== Verify L2TP tunnels and Redundancy On DUT ====
      
        VERIFY L2TP REDUNDANCY ON DUT
        ...    NOKIA   
        ...    ${pc_lo_ip}

Run L2TP Redundancy Verification On PC
    [Documentation]    Verify L2TP  tunnels and Redundancy On PC
    Log To Console    ==== Verify L2TP tunnels and Redundancy On PC ====
      
        VERIFY L2TP REDUNDANCY ON PC
        ...    ${pc_name}
        ...    ${pc_pass}
        ...    ${dut_lo_ip}
          


Run L2TP Teardown
    [Documentation]    Loop through all teardown L2TP tunnels
    Log To Console    ==== Teardown L2TP tunnels ====

    # Get L2TP tunnel list
        FOR    ${tunnel}    IN    @{L2TP_DUT_LIST}
            ${tunnel_id}=         Set Variable    ${tunnel["tunnel_id"]}
            ${session_id}=        Set Variable    ${tunnel["session_id"]}
            TEARDOWN L2TP TUNNEL
            ...    NOKIA  
            ...    ${dut_pass}
            ...    ${tunnel_id}  
            ...    ${session_id}   
        END         
        
        FOR    ${tunnel}    IN    @{L2TP_PC_LIST}
            ${tunnel_id}=         Set Variable    ${tunnel["tunnel_id"]}
            ${session_id}=        Set Variable    ${tunnel["session_id"]}
            TEARDOWN L2TP TUNNEL
            ...    ${pc_name}  
            ...    ${pc_pass}
            ...    ${tunnel_id}  
            ...    ${session_id} 
        END        
        





