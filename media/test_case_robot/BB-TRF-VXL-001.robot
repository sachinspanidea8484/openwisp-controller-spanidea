*** Settings ***
Library           ../../resources/keywords/BB-TRF-VXL-001.py
Library           JSONLibrary
Library           OperatingSystem
Library           Collections
Library           SSHLibrary
Library           String
Library           BuiltIn
Resource          ../../resources/keywords/common_keywords.robot

#Suite Setup       Initialize_Custom_Log_File
Suite Teardown    Close All Connections
Suite Setup       Full Suite Setup


*** Variables ***
${DEVICE_JSON}    ${EMPTY}
${TEST_JSON}      ${EMPTY}
${LOG_FOLDER}     ${CURDIR}/../../logs

*** Test Cases ***
BB- TRF-VXL-001 End-to-End Validation
    [Documentation]    End-to-end modem + VxLAN + RPi connectivity validation
    [Tags]    BB-TRF-VXL-001
    
    Log To Console                ===== Starting modem test case===
    Log Message To Custom File    "===== Starting modem test case==="
    
    ${devices}=    Evaluate    json.loads("""${DEVICE_JSON}""")    json
    ${testcfg}=    Evaluate    json.loads("""${TEST_JSON}""")    json
    ${vxlan_list}=    Get From Dictionary    ${testcfg}    vxlan
    ${bb}=         Set Variable    ${devices['BB']}
    ${PING_IP}=    Set Variable    ${testcfg['REMOTE_PING_IP']}



    # Step 0: Connect BB
    Log To Console                === Connecting BB ===
    Log Message To Custom File    "=== Connecting BB ==="
    
    ${bb_ssh}=     Connect_Device    ${devices['BB']}
    
    Log To Console                === BB Connected Successfully ===
    Log Message To Custom File    "=== BB Connected Successfully ==="

    # Step 1: Connect RPis dynamically
    Log To Console                ==== Connecting RPis dynamically ====
    Log Message To Custom File    "==== Connecting RPis dynamically ===="
    
    ${rpi_list}=   Evaluate    [v for k,v in ${testcfg}.items() if k.startswith('RPi')]
    ${rpi_connections}=    Connect_All_RPis    ${rpi_list}
    
    Log To Console                ==== RPis Connected Successfully ====
    Log Message To Custom File    "==== RPis Connected Successfully ====

    # Step 2: Ensure modem is connected
    Log To Console                === Ensuring modem is connected ===
    Log Message To Custom File    "=== Ensuring modem is connected ==="
    
    Ensure_Modem_Connected    ${devices['BB']}    ${bb_ssh}    
    ${modem_ip}=   Get_Modem_IP    ${bb_ssh}    
    ${net_type}=   Check_Signal_Info    ${bb_ssh} 
    
    Log To Console                === Modem connected successfully with IP ${modem_ip} ===
    Log Message To Custom File    "=== Modem connected successfully with IP ${modem_ip} ==="  
    
    
    # Step 4: Check all RPi routing
    Log To Console                === Checking RPis routing===
    Log Message To Custom File    "=== Checking RPis routing==="
    
    ${rpi_routes}=    Check_RPi_Routing_Dynamic    ${rpi_connections}
    
    Log To Console                === RPi routing verified ===
    Log Message To Custom File    "=== RPi routing verified ==="
    
      
    # Step 5: Setup VxLAN Interface on BB
    Log To Console                === Setting up VxLAN interface on BB ===
    Log Message To Custom File    "=== Setting up VxLAN interface on BB ==="
    
    Setup_VXLAN_Interface    ${bb_ssh}    ${bb["vxlan_name"]}    ${bb["vxlan_id"]}    ${bb["underlay_iface"]}    ${bb["dstport"]}    ${bb["bridge_name"]}    ${bb["overlay_ip"]}
   
    
    Log To Console                === VxLAN configured successfully ===
    Log Message To Custom File    "=== VxLAN configured successfully ==="

    # Step 6: SetuP VxLAN Interfcae on RPis
    Log To Console                === Setting up VxLAN interface on RPis ===
    Log Message To Custom File    "=== Setting up VxLAN interface on RPis ==="
    
    Setup_RPi_VXLANs    ${rpi_connections}    ${vxlan_list}    ${modem_ip}
    
    Log To Console                === RPis VxLAN configured successfully ===
    Log Message To Custom File    "=== RPis VxLAN configured successfully ==="

    # Step 7: Collect baseline metrics
    Log To Console                === Collecting baseline metrics ===
    Log Message To Custom File    "=== Collecting baseline metrics ==="
    
    Collect_Baseline_Metrics    ${bb_ssh}    ${testcfg['REMOTE_PING_IP']}    ${testcfg['IDLE_PING_DURATION']}
    
    Log To Console                === Baseline metrics collection complete ===
    Log Message To Custom File    "=== Baseline metrics collection complete ==="

    # Step 8: Check all RPi connectivity
    Log To Console                === Checking RPis connectivity ===
    Log Message To Custom File    "=== Checking RPis connectivity ==="
    
    ${ping_results}=  Ping_All_RPis_VXLAN    ${rpi_connections}    ${vxlan_list}    ${bb["overlay_ip"]}
    Should Be True    ${ping_results}    One or more RPis failed to ping the remote IP!
    
    Log To Console                === RPis connectivity verified ===
    Log Message To Custom File    "=== RPis connectivity verified ==="


    # Step 7: Log live metrics during stability test
    Log To Console                === Starting traffic test & logging metrics ===
    Log Message To Custom File    "=== Starting traffic test & logging metrics ==="
    
    ${tid}=    Log_System_Metrics    ${bb_ssh}    interval=${testcfg['METRICS_INTERVAL']}
    Sleep    ${testcfg['TEST_DURATION']}
    Stop_System_Metrics    ${tid}
    
    Log To Console                === VxLAN test completed ===
    Log Message To Custom File    "=== VxLAn test completed ==="

     # Step 8:Cleanup WWAN Default Route 
    Log To Console                === Ensuring BB & RPIs VxLAN cleanup ===
    Log Message To Custom File    "===Ensuring BB & RPIs VxLAN cleanup==="
    
    cleanup_bb_vxlan  ${bb_ssh}    ${bb["vxlan_name"]}    ${bb["bridge_name"]}    ${bb["overlay_ip"]}
    cleanup_rpis_vxlan   ${rpi_connections}
    Cleanup_RPi_Default_Route     ${rpi_connections}
      
    Log To Console                === Cleanup BB & RPis VxLAN successfully ===
    Log Message To Custom File    "=== Cleanup BB & RPis VxLAN successfully ==="
    
*** Keywords ***
Full Suite Setup
    [Documentation]    Prepare environment before running the test suite
    Log To Console                Running Full Suite Setup...
    Log Message To Custom File    "Running Full Suite Setup..."
    Create Directory              ${LOG_FOLDER}
    Initialize Custom Log File
    Log To Console                Custom Log File Initialized
    Log Message To Custom File    "Custom Log File Initialized"
            
