*** Settings ***
Library           ../../resources/keywords/check_firewall.py
Library           OperatingSystem
Library           JSONLibrary
Library           Collections
Library           String
Library           BuiltIn
Resource          ../../resources/keywords/common_keywords.robot
Suite Setup       Initialize Custom Log File

*** Variables ***
${DEVICE_JSON}     ${EMPTY}
${TEST_JSON}       ${EMPTY}
${LOG_FOLDER}      ${CURDIR}/../../logs

*** Test Cases ***
Firewall Rule Ping Behavior Test
    [Tags]    

    NEWS Device Info
    Delete Existing Ping Rules
    Add Block Ping Rule And Verify
    Delete Block Rule And Add Allow Rule
    Verify Ping Is Allowed

*** Keywords ***

Load Device Info
    Log Message To Custom File   📁 Loading config from provided variables
    ${device_config}=    Evaluate    json.loads("""${DEVICE_JSON}""")    json
    ${test_config}=      Evaluate    json.loads("""${TEST_JSON}""")      json

    # Device (BB / OpenWRT)
    ${BB}=    Set Variable    ${device_config["BB"]}
    ${ow_ip}=    Set Variable    ${BB["ip"]}
    ${ow_user}=  Set Variable    ${BB["username"]}
    ${ow_pass}=  Set Variable    ${BB["password"]}

    # Test Machine (PC / RPi)
    ${PC}=    Set Variable    ${test_config["PC"]}
    ${rpi_ip}=    Set Variable    ${PC["ip"]}
    ${rpi_user}=  Set Variable    ${PC["username"]}
    ${rpi_pass}=  Set Variable    ${PC["password"]}
    ${ping_ip}=   Set Variable    ${PC["ping ip"]}

    # Make available to all test steps
    Set Suite Variable    ${ow_ip}
    Set Suite Variable    ${ow_user}
    Set Suite Variable    ${ow_pass}
    Set Suite Variable    ${rpi_ip}
    Set Suite Variable    ${rpi_user}
    Set Suite Variable    ${rpi_pass}
    Set Suite Variable    ${ping_ip}

    # Pass ping target into Python global
    Set Ping Ip           ${ping_ip}

Delete Existing Ping Rules
    Log To Console               ==== Deleting any existing Allow/Block Ping Rules ====
    Log Message To Custom File   ==== Deleting any existing Allow/Block Ping Rules ====
    Delete Allow Ping Rules      ${ow_ip}    ${ow_user}    ${ow_pass}

Add Block Ping Rule And Verify
    Log To Console               ==== Adding Block-Ping rule ====
    Log Message To Custom File   ==== Adding Block-Ping rule ====
    Add Block Ping Rule          ${ow_ip}    ${ow_user}    ${ow_pass}

    Log To Console               ==== Verifying Ping is Blocked from PC ====
    Log Message To Custom File   ==== Verifying Ping is Blocked from PC ====
    Verify Ping Failure          ${rpi_ip}    ${rpi_user}    ${rpi_pass}

Delete Block Rule And Add Allow Rule
    Log To Console               ==== Deleting Block-Ping rule ====
    Log Message To Custom File   ==== Deleting Block-Ping rule ====
    Delete Allow Ping Rules      ${ow_ip}    ${ow_user}    ${ow_pass}

    Log To Console               ==== Adding Allow-Ping rule ====
    Log Message To Custom File   ==== Adding Allow-Ping rule ====
    Add Allow Ping Rule          ${ow_ip}    ${ow_user}    ${ow_pass}

Verify Ping Is Allowed
    Log To Console               ==== Verifying Ping is Allowed from PC ====
    Log Message To Custom File   ==== Verifying Ping is Allowed from PC ====
    Verify Ping Success          ${rpi_ip}    ${rpi_user}    ${rpi_pass}

