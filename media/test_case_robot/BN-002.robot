*** Settings ***
Library           ../../resources/keywords/BN-002.py
Library           JSONLibrary
Library           BuiltIn
Library           Collections

*** Variables ***
${DEVICE_JSON}     ${EMPTY}
${TEST_JSON}       ${EMPTY}
${LOG_FOLDER}      ${CURDIR}/../../logs

*** Test Cases ***
Verify SSH Access - PC Then BB
    [Tags]    BN-002
    Load Device Info
     Log To Console    ==== PING BB ====
     Log To Console    ==== Test Case Complete ====



*** Keywords ***
Load Device Info
    ${BB}=    Evaluate    json.loads("""${DEVICE_JSON}""")    json

 