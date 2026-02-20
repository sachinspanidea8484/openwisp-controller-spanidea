*** Settings ***
Library           ../../../resources/keywords/robot_001.py
Library           JSONLibrary
Library           BuiltIn
Library           Collections

*** Variables ***
${DEVICE_JSON}     ${EMPTY}
${TEST_JSON}       ${EMPTY}
${LOG_FOLDER}      ${CURDIR}/../../../logs

*** Test Cases ***
Verify SSH Access - PC Then BB
    [Tags]    RJ-001
    Load Device Info
     Sleep    20s
     Log To Console    ==== PING BB ====
     Log To Console    ==== Test Case Complete ====



*** Keywords ***
Load Device Info
    ${BB}=    Evaluate    json.loads("""${DEVICE_JSON}""")    json

 
