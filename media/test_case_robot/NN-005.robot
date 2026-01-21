*** Settings ***
Library    ../../resources/keywords/NN-005.py


*** Variables ***
${STATIC_MESSAGE}    NN-005 static test executed


*** Test Cases ***
NN-005 Basic Test
    [Tags]    NN-005
    Print Static Message


*** Keywords ***
Print Static Message
    Log    ${STATIC_MESSAGE}

