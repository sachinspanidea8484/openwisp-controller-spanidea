*** Settings ***
Library           ../../resources/keywords/NS4500.py
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
    [Tags]    NS4500
    Load Device Info
    Log Message To Custom File   📁 Loading config from provided variables
    Log Message To Custom File   ==== Verifying chained SSH: PC -> BB ====
    ${result}=    SSH PC Then BB    ${pc_ip}    ${pc_user}    ${pc_pass}    ${bb_ip}    ${bb_user}    ${bb_pass}
    Log Message To Custom File   Expected result: SUCCESS, Actual result: ${result}
    Run Keyword If    '${result}' != 'SUCCESS'    Fail    SSH Access Test Failed

*** Keywords ***
Load Device Info
    ${BB}=    Evaluate    json.loads("""${DEVICE_JSON}""")    json
    ${PC}=    Evaluate    json.loads("""${TEST_JSON}""")      json
    Set Suite Variable    ${bb_ip}    ${BB["BB"]["ip"]}
    Set Suite Variable    ${bb_user}  ${BB["BB"]["user"]}
    Set Suite Variable    ${bb_pass}  ${BB["BB"]["password"]}
    Set Suite Variable    ${pc_ip}    ${PC["PC"]["ip"]}
    Set Suite Variable    ${pc_user}  ${PC["PC"]["user"]}
    Set Suite Variable    ${pc_pass}  ${PC["PC"]["password"]}
 
