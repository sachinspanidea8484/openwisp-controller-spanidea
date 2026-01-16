*** Settings ***
Library           ../../resources/keywords/NSD-003.py
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
    [Tags]    NSD-003
    Load Device Info
    Log Message To Custom File   📁 Loading config from provided variables
    Log Message To Custom File   ==== Verifying chained SSH: PC -> BB ====


*** Keywords ***
Load Device Info
    ${BB}=    Evaluate    json.loads("""${DEVICE_JSON}""")    json

 
