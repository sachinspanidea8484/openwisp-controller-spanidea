*** Settings ***
Library           ../../resources/keywords/ETH-001.py
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
    [Tags] ETH-001
    Log To Console    ==== STEP ONE RUN ====
    Log To Console    ==== Test Case Pass ====





*** Keywords ***
Load Device Info
    ${BB}=    Evaluate    json.loads("""${DEVICE_JSON}""")    json

 
