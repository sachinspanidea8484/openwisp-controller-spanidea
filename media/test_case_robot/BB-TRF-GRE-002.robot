*** Settings ***
Library           ../../../resources/keywords/BB-TRF-GRE-002.py
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
BB-TRF-GRE-002 GRE Tunnel Redundancy End-to-End Test
    [Tags]    BB-TRF-GRE-002

    # Load Device Info
    Log Message To Custom File   ==== Starting GRE Tunnel Redundancy Test ====
   
    Run GRE Setup On DUT
    Run GRE Setup On PC
    Setup ECMP Route On DUT
    Setup ECMP Route On PC
    Run GRE Redundancy Verification On DUT
    Run GRE Redundancy Verification On PC
    Run GRE Teardown
   
    Log Message To Custom File    GRE Tunnel Redundancy End-to-End Test Successful


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

    # GRE Parameter Lists
    ${GRE_BB_LIST}=     Set Variable    ${test_config["GRE_BB"]}
    ${GRE_DC_LIST}=     Set Variable    ${test_config["GRE_DC"]}

    # GRE Tunnel IPs
    ${bb_tunnel_ip}=       Set Variable    ${test_config["bb_tunnel_ip"]}
    ${dc_tunnel_ip}=       Set Variable    ${test_config["dc_tunnel_ip"]}


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
    Set Suite Variable    ${GRE_BB_LIST}
    Set Suite Variable    ${GRE_DC_LIST}
    Set Suite Variable    ${bb_tunnel_ip}
    Set Suite Variable    ${dc_tunnel_ip}
 
   
    Log To Console    ------------------------------------------------------------
    Log To Console    Configuration Loaded:
    Log To Console    - Protocol: ${CONNECTION_PROTOCOL}
    Log To Console    - DUT IP: ${dut_ip}
    Log To Console    - Device ID: ${DEVICE_ID}
    Log To Console    - Execution ID: ${EXECUTION_ID}
    Log To Console    - Devices Loaded: ${DEVICE_COUNT}
    Log To Console    ------------------------------------------------------------


# ==========================================================
# WRAPPER KEYWORDS FOR GRE REDUNDANCY (SSH or MQTT)
# ==========================================================


Run GRE Setup On DUT
    [Documentation]    Creating GRE tunnel on DUT
    Log To Console    ==== Running GRE Setup On DUT ====

        # Get GRE tunnel list
        FOR    ${tunnel}    IN    @{GRE_BB_LIST}
            ${tunnel_name}=       Set Variable    ${tunnel["name"]}
            ${underlay_iface}=    Set Variable    ${tunnel["iface"]}
            ${local_ip}=          Set Variable    ${tunnel["local_ip"]}
            ${remote_ip}=         Set Variable    ${tunnel["remote_ip"]}
            ${tunnel_ip}=         Set Variable    ${tunnel["overlay_ip"]}

            SET UP GRE TUNNEL ON BB
            ...    DUT
            ...    ${tunnel_name}    
            ...    ${underlay_iface}
            ...    ${local_ip}    
            ...    ${remote_ip}    
            ...    ${tunnel_ip}  
        END



Run GRE Setup On PC
    [Documentation]    Creating GRE tunnel on DC
    Log To Console    ==== Running GRE Setup On DC ====

        # Get GRE tunnel list
        FOR    ${tunnel}    IN    @{GRE_DC_LIST}
            ${tunnel_name}=       Set Variable    ${tunnel["name"]}
            ${underlay_iface}=    Set Variable    ${tunnel["iface"]}
            ${local_ip}=          Set Variable    ${tunnel["local_ip"]}
            ${remote_ip}=         Set Variable    ${tunnel["remote_ip"]}
            ${tunnel_ip}=         Set Variable    ${tunnel["overlay_ip"]}

            SET UP GRE TUNNEL ON DC
            ...    ${pc_name}    
            ...    ${pc_pass}
            ...    ${tunnel_name}    
            ...    ${underlay_iface}
            ...    ${local_ip}    
            ...    ${remote_ip}    
            ...    ${tunnel_ip}  

        END


Setup ECMP Route On DUT
    [Documentation]    Setting ECMP route on DUT
    Log To Console    ==== Setting ECMP Route On DUT ====

        ${peer_gre1_ip}=    Set Variable    ${GRE_DC_LIST[0]["overlay_ip"]}
        ${peer_gre2_ip}=    Set Variable    ${GRE_DC_LIST[1]["overlay_ip"]}

        ECMP ROUTE SETUP ON BB
        ...    DUT
        ...    ${bb_tunnel_ip}    
        ...    ${dc_tunnel_ip}
        ...    ${peer_gre1_ip}    
        ...    ${peer_gre2_ip}


Setup ECMP Route On PC
    [Documentation]    Setting ECMP route on PC
    Log To Console    ==== Setting ECMP Route On PC ====

        ${peer_gre1_ip}=    Set Variable    ${GRE_BB_LIST[0]["overlay_ip"]}
        ${peer_gre2_ip}=    Set Variable    ${GRE_BB_LIST[1]["overlay_ip"]}

        ECMP ROUTE SETUP ON DC
        ...    ${pc_name}    
        ...    ${pc_pass}
        ...    ${dc_tunnel_ip}    
        ...    ${bb_tunnel_ip}
        ...    ${peer_gre1_ip}    
        ...    ${peer_gre2_ip}



Run GRE Redundancy Verification On DUT
    [Documentation]    Verify GRE  tunnels and Redundancy 
    Log To Console    ==== Verify GRE tunnels and Redundancy On DUT ====

        # Extract both GRE Name  
        ${gre_a_name}=    Set Variable    ${GRE_BB_LIST[0]["name"]}
        ${gre_b_name}=    Set Variable    ${GRE_BB_LIST[1]["name"]}
      
        VERIFY GRE REDUNDANCY ON BB
        ...    DUT
        ...    ${gre_a_name}   
        ...    ${gre_b_name}    
        ...    ${dc_tunnel_ip}



Run GRE Redundancy Verification On PC
    [Documentation]    Verify GRE  tunnels and Redundancy 
    Log To Console    \n==== Verify GRE tunnels and Redundancy On PC ====

        # Extract both GRE Name  
        ${gre_a_name}=    Set Variable    ${GRE_DC_LIST[0]["name"]}
        ${gre_b_name}=    Set Variable    ${GRE_DC_LIST[1]["name"]}

        VERIFY GRE REDUNDANCY ON DC
        ...    ${pc_name}    
        ...    ${pc_pass}
        ...    ${gre_a_name}   
        ...    ${gre_b_name}    
        ...    ${bb_tunnel_ip}



Run GRE Teardown
    [Documentation]    Loop through all teardown GRE tunnels
    Log To Console    ==== Teardown GRE tunnels ====

    # Get GRE tunnel list
        FOR    ${tunnel}    IN    @{GRE_BB_LIST}
            ${tunnel_name}=       Set Variable    ${tunnel["name"]}
            TEARDOWN GRE TUNNEL
            ...    DUT  
            ...    ${dut_pass}
            ...    ${tunnel_name}  
        END   
        
        FOR    ${tunnel}    IN    @{GRE_DC_LIST}
            ${tunnel_name}=       Set Variable    ${tunnel["name"]}
            TEARDOWN GRE TUNNEL
            ...    ${pc_name}    
            ...    ${pc_pass}
            ...    ${tunnel_name}        
   
        END





