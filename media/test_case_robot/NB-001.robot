*** Settings ***
Library           ../../resources/keywords/NB-001.py
Library           JSONLibrary
Library           BuiltIn
Library           Collections

*** Variables ***
${DEVICE_JSON}     ${EMPTY}
${TEST_JSON}       ${EMPTY}
${LOG_FOLDER}      ${CURDIR}/../../logs

*** Test Cases ***
Verify SSH Access - PC Then BB
    [Tags]    NB-001
    Load Device Info
     Log To Console    ==== PING BB ====
     Log To Console    ==== Test Case Complete ====



*** Keywords ***
Load Device Info
    ${BB}=    Evaluate    json.loads("""${DEVICE_JSON}""")    json

 