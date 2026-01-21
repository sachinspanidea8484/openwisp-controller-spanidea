*** Settings ***
Library           ../../resources/keywords/NI-013.py
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
BB-TRF-4G5G-001 End-to-End Validation
    [Documentation]    Full BB-TRF-4G5G-001 workflow: modem, Ethernet (lan)<---> 4G/5G WAN, RPi ping, metrics, stability
    [Tags]    <CHANGE_ON_RUNTIME>
    
    Log To Console                ===== Starting modem test case===
    Log Message To Custom File    "===== Starting modem test case==="
    
    # Load JSON configs
    ${devices}=    Evaluate    json.loads("""${DEVICE_JSON}""")    json
    ${testcfg}=    Evaluate    json.loads("""${TEST_JSON}""")      json

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
    Ensure_WWAN_Default_Route    ${bb_ssh}    wwan0    ${modem_ip}
      
    Log To Console                === Modem connected successfully with IP ${modem_ip} ===
    Log Message To Custom File    "=== Modem connected successfully with IP ${modem_ip} ==="
    

    # Step 3: Collect baseline metrics
    Log To Console                === Collecting baseline metrics ===
    Log Message To Custom File    "=== Collecting baseline metrics ==="
    
    Collect_Baseline_Metrics    ${bb_ssh}    ${testcfg['REMOTE_PING_IP']}    ${testcfg['IDLE_PING_DURATION']}
    
    Log To Console                === Baseline metrics collection complete ===
    Log Message To Custom File    "=== Baseline metrics collection complete ==="

     # Step 4: Check all RPi routing & connectivity
    Log To Console                === Checking RPi routing & connectivity ===
    Log Message To Custom File    "=== Checking RPi routing & connectivity ==="
    
    ${rpi_routes}=    Check_RPi_Routing_Dynamic    ${rpi_connections}
    ${ping_results}=  Ping_All_RPis    ${rpi_connections}    remote_ip=${testcfg['REMOTE_PING_IP']}
    
    Log To Console                === RPi routing & connectivity verified ===
    Log Message To Custom File    "=== RPi routing & connectivity verified ==="
    
    # Step 5: Log live metrics during stability test
    Log To Console                === Starting traffic test & logging metrics ===
    Log Message To Custom File    "=== Starting traffic test & logging metrics ==="
    
    ${tid}=    Log_System_Metrics    ${bb_ssh}    interval=${testcfg['METRICS_INTERVAL']}
    Sleep    ${testcfg['TEST_DURATION']}
    Stop_System_Metrics    ${tid}
    
    Log To Console                === Traffic test completed ===
    Log Message To Custom File    "=== Traffic test completed ==="

     # Step 6:Cleanup WWAN Default Route 
    Log To Console                === Ensuring the wwan default route cleanup ===
    Log Message To Custom File    "===Ensuring the wwan default route cleanup==="
    
    Cleanup_RPi_Default_Route     ${rpi_connections}
    Cleanup_WWAN_Default_Route    ${bb_ssh}    wwan0    ${modem_ip}
      
    Log To Console                === Cleanup wwano default route successfully ===
    Log Message To Custom File    "=== Cleanup wwano default route successfully ==="

    # Step 7: Optional reboot & reconnect
    #${reconnect_time}=    Reboot_And_Measure    ${devices['BB']}    ${bb_ssh}    ${testcfg['RECONNECT_TIMEOUT']}
    
*** Keywords ***
Full Suite Setup
    [Documentation]    Prepare environment before running the test suite
    Log To Console                Running Full Suite Setup...
    Log Message To Custom File    "Running Full Suite Setup..."
    Create Directory              ${LOG_FOLDER}
    Initialize Custom Log File
    Log To Console                Custom Log File Initialized
    Log Message To Custom File    "Custom Log File Initialized"
    
