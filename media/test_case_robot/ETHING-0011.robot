*** Settings ***
Library           ../../resources/keywords/ETHING-0011.py
Library           JSONLibrary
Library           BuiltIn
Library           Collections
Suite Setup       Initialize Custom Log File

*** Variables ***
${DEVICE_JSON}     ${EMPTY}
${TEST_JSON}       ${EMPTY}
${LOG_FOLDER}      ${CURDIR}/../../logs

*** Test Cases ***
Verify SSH Access - PC Then BB
    [Tags]    ETHING-0011
    Load Device Info
    Log Message To Custom File   Test Case Passed


*** Keywords ***
Load Device Info
    ${BB}=    Evaluate    json.loads("""${DEVICE_JSON}""")    json

 