
*** Settings ***
Library           ../../../resources/keywords/BB-TRF-VXL-002.py
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
BB-TRF-VXL-002 VXLAN Tunnel Redundancy End-to-End Test
    [Tags]    BB-TRF-VXL-002

    #Load Device Info
    Log Message To Custom File   ==== Starting VXLAN Tunnel Redundancy Test ====

    Run VXLAN Setup On BB
    Run VXLAN Setup On DC
    Setup VXLAN Bridge On BB
    Setup VXLAN Bridge On DC
    Run VXLAN Redundancy Verification On BB
    Run VXLAN Redundancy Verification On DC
    Run VXLAN Teardown
  
    Log Message To Custom File   VXLAN Tunnel Redundancy End-to-End Test Successful


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

    # VXLAN Parameter Lists
    ${VXLAN_BB_LIST}=     Set Variable    ${test_config["VXLAN_BB"]}
    ${VXLAN_DC_LIST}=     Set Variable    ${test_config["VXLAN_DC"]}

    # vxlan Tunnel IPs
    ${bb_tunnel_ip}=      Set Variable    ${test_config["bb_tunnel_ip"]}
    ${dc_tunnel_ip}=      Set Variable    ${test_config["dc_tunnel_ip"]}
    ${br_name}=           Set Variable    ${test_config["br_name"]}

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
    Set Suite Variable    ${VXLAN_BB_LIST}
    Set Suite Variable    ${VXLAN_DC_LIST}
    Set Suite Variable    ${bb_tunnel_ip}
    Set Suite Variable    ${dc_tunnel_ip}
    Set Suite Variable    ${br_name}
 
    Log To Console    ------------------------------------------------------------
    Log To Console    Configuration Loaded:
    Log To Console    - Protocol: ${CONNECTION_PROTOCOL}
    Log To Console    - DUT IP: ${dut_ip}
    Log To Console    - Device ID: ${DEVICE_ID}
    Log To Console    - Execution ID: ${EXECUTION_ID}
    Log To Console    - Devices Loaded: ${DEVICE_COUNT}
    Log To Console    ------------------------------------------------------------


# ==========================================================
# WRAPPER KEYWORDS FOR VXLAN REDUNDANCY (SSH or MQTT)
# ==========================================================

Run VXLAN Setup On BB
    Log To Console    ==== Running VXLAN Setup On BB ====

        # Get VXLAN tunnel list
        FOR    ${tunnel}    IN    @{VXLAN_BB_LIST}
            ${tunnel_name}=       Set Variable    ${tunnel["name"]}
            ${vxlan_id}=          Set Variable    ${tunnel["vxlan_id"]}
            ${iface}=             Set Variable    ${tunnel["iface"]}
            ${local_ip}=          Set Variable    ${tunnel["local_ip"]}
            ${remote_ip}=         Set Variable    ${tunnel["remote_ip"]}
            
            SET UP VXLAN TUNNEL ON BB
            ...    DUT
            ...    ${tunnel_name}    
            ...    ${vxlan_id}   
            ...    ${iface}
            ...    ${local_ip}    
            ...    ${remote_ip} 

        END


Run VXLAN Setup On DC
    Log To Console    ==== Running VXLAN Setup On DC ====

        # Get VXLAN tunnel list
        FOR    ${tunnel}    IN    @{VXLAN_DC_LIST}
            ${tunnel_name}=       Set Variable    ${tunnel["name"]}
            ${vxlan_id}=          Set Variable    ${tunnel["vxlan_id"]}
            ${iface}=             Set Variable    ${tunnel["iface"]}
            ${local_ip}=          Set Variable    ${tunnel["local_ip"]}
            ${remote_ip}=         Set Variable    ${tunnel["remote_ip"]}
           
           
            SET UP VXLAN TUNNEL ON DC
            ...    ${pc_name}    
            ...    ${pc_pass}
            ...    ${tunnel_name}    
            ...    ${vxlan_id}   
            ...    ${iface}
            ...    ${local_ip}    
            ...    ${remote_ip} 

        END
 

Setup VXLAN Bridge On BB
    Log To Console    ==== Setting VXLAN Bridge On BB ====

        ATTACH VXLANS TO BRIDGE ON BB
        ...    DUT 
        ...    ${br_name}    
        ...    ${bb_tunnel_ip}
        


Setup VXLAN Bridge On DC
    Log To Console    ==== Setting VXLAN Bridge On DC ====

        ATTACH VXLANS TO BRIDGE ON DC
        ...    ${pc_name}    
        ...    ${pc_pass}
        ...    ${br_name}    
        ...    ${dc_tunnel_ip}
  


Run VxLAN Redundancy Verification On BB
    [Documentation]    Verify VXLAN tunnels and Redundancy 
    Log To Console    ==== Verify VXLAN tunnels and Redundancy On BB ====

        # Extract both VXLAN Name  
        ${vxlan_a_name}=    Set Variable    ${VXLAN_BB_LIST[0]["name"]}
        ${vxlan_b_name}=    Set Variable    ${VXLAN_BB_LIST[1]["name"]}

        VERIFY VXLAN REDUNDANCY ON BB
        ...    DUT
        ...    ${vxlan_a_name}   
        ...    ${vxlan_b_name}    
        ...    ${dc_tunnel_ip}



Run VxLAN Redundancy Verification On DC
    [Documentation]    Verify VXLAN tunnels and Redundancy 
    Log To Console    ==== Verify VXLAN tunnels and Redundancy On DC ====

 
       # Extract both VXLAN Name  
        ${vxlan_a_name}=    Set Variable    ${VXLAN_DC_LIST[0]["name"]}
        ${vxlan_b_name}=    Set Variable    ${VXLAN_DC_LIST[1]["name"]}

        VERIFY VXLAN REDUNDANCY ON DC
        ...    ${pc_name}    
        ...    ${pc_pass}
        ...    ${vxlan_a_name}   
        ...    ${vxlan_b_name}    
        ...    ${bb_tunnel_ip}

   


Run VXLAN Teardown
    [Documentation]    Loop through all teardown VXLAN tunnels

    # Get VXLAN tunnel list
        FOR    ${tunnel}    IN    @{VXLAN_BB_LIST}
            ${tunnel_name}=       Set Variable    ${tunnel["name"]}
         
            TEARDOWN VXLAN AND BRIDGE
            ...    DUT    
            ...    ${dut_pass}
            ...    ${tunnel_name}    
            ...    ${br_name}
        END

        FOR    ${tunnel}    IN    @{VXLAN_DC_LIST}
            ${tunnel_name}=       Set Variable    ${tunnel["name"]}
           
            TEARDOWN VXLAN AND BRIDGE
            ...    ${pc_name}    
            ...    ${pc_pass}
            ...    ${tunnel_name}    
            ...    ${br_name} 
        END

            



