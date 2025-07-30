# openwisp_test_management/tasks.py
import logging
from celery import shared_task
from django.utils import timezone
from openwisp_controller.connection.connectors.ssh import Ssh
from openwisp_controller.connection.models import DeviceConnection
from .swapper import load_model
from .base.models import TestExecutionStatus
import requests



# Configure logger for this module
logger = logging.getLogger(__name__)

# Load models using swapper pattern for better modularity
TestSuiteExecution = load_model("TestSuiteExecution")
TestSuiteExecutionDevice = load_model("TestSuiteExecutionDevice")
TestCaseExecution = load_model("TestCaseExecution")
TestSuiteCase = load_model("TestSuiteCase")

# Device Execution Type Configuration
DEVICE_EXECUTION_TYPE = 2 # 1 for SSH, 2 for NB_API (default is SSH)

# Robot Framework API Server Configuration
# ROBOT_API_SERVER = getattr(settings, 'ROBOT_API_SERVER', 'http://localhost:5000')
# ROBOT_API_TIMEOUT = getattr(settings, 'ROBOT_API_TIMEOUT', 300)  # 5 minutes default

@shared_task
def execute_test_suite(execution_id):
    


    """
    Main task to execute a test suite on all devices.
    
    This is the entry point for test suite execution. It:
    1. Retrieves the test suite execution record
    2. Gets all associated device executions
    3. Launches parallel execution tasks for each device
    
    Args:
        execution_id (int): Primary key of the TestSuiteExecution record
        
    Returns:
        None
        
    Raises:
        Exception: Logs any errors that occur during execution setup
    """
    logger.info(f"Starting test suite execution with ID: {execution_id}")
    # print(f"🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️: {execution_id})")
    try:
        # Retrieve the test suite execution record
        execution = TestSuiteExecution.objects.get(pk=execution_id)
        logger.info(f"Retrieved test suite execution: {execution}")
        print(f"[TASK] execute_test_suite - Retrieved execution: {execution}")
        
        # Get all device executions associated with this test suite execution
        device_executions = TestSuiteExecutionDevice.objects.filter(
            test_suite_execution=execution
        ).select_related('device')
        
        device_count = device_executions.count()
        logger.info(f"Found {device_count} devices to execute tests on")
        print(f"[TASK] execute_test_suite - Found {device_count} devices")
        
        # Launch individual device executions in parallel
        for device_execution in device_executions:
            logger.info(f"Launching tests on device: {device_execution.device.name} (ID: {device_execution.id})")
            print(f"[TASK] execute_test_suite - Launching device execution ID: {device_execution.id} for device: {device_execution.device.name}")
            
            # Queue the device execution task
            execute_tests_on_device.delay(device_execution.id)
            
        logger.info(f"Successfully queued test execution for {device_count} devices")
        print(f"[TASK] execute_test_suite - Successfully queued {device_count} device executions")
        
    except TestSuiteExecution.DoesNotExist:
        error_msg = f"Test suite execution with ID {execution_id} not found"
        logger.error(error_msg)
        print(f"[ERROR] execute_test_suite - {error_msg}")
        
    except Exception as e:
        error_msg = f"Error executing test suite {execution_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        print(f"[ERROR] execute_test_suite - {error_msg}")


@shared_task
def execute_tests_on_device(device_execution_id):
    """
    Execute all test cases on a single device by launching parallel test executions.
    """
    logger.info(f"Starting device execution with ID: {device_execution_id}")
    print(f"[TASK] execute_tests_on_device - Starting device execution ID: {device_execution_id}")

    try:
        # Retrieve the device execution record
        device_execution = TestSuiteExecutionDevice.objects.get(pk=device_execution_id)
        logger.info(f"Retrieved device execution: {device_execution}")
        print(f"[TASK] execute_tests_on_device - Retrieved device execution: {device_execution}")
        
        device = device_execution.device
        test_suite_execution = device_execution.test_suite_execution
        
        logger.info(f"Device: {device.name} (ID: {device.id})")
        logger.info(f"Test suite: {test_suite_execution.test_suite.name}")
        print(f"[TASK] execute_tests_on_device - Device: {device.name} (ID: {device.id})")
        print(f"[TASK] execute_tests_on_device - Test suite: {test_suite_execution.test_suite.name}")
        
        # Update device execution status to running
        device_execution.status = 'running'
        device_execution.started_at = timezone.now()
        device_execution.save()
        
        logger.info(f"Updated device execution status to 'running' at {device_execution.started_at}")
        print(f"[TASK] execute_tests_on_device - Updated status to 'running' at {device_execution.started_at}")
        
        # Check device connection
        device_conn = None
        has_connection = False
        try:
            device_conn = DeviceConnection.objects.get(
                device=device,
                enabled=True
            )
            has_connection = True
            logger.info(f"Found working device connection: {device_conn}")
            print(f"[TASK] execute_tests_on_device - Found working connection: {device_conn}")
            
        except DeviceConnection.DoesNotExist:
            has_connection = False
            error_msg = f"No working connection found for device {device.name}"
            logger.warning(error_msg)
            print(f"[WARNING] execute_tests_on_device - {error_msg}")
        
        # Get ordered test cases from the test suite
        test_cases = test_suite_execution.test_suite.get_ordered_test_cases()
        total_test_cases = len(test_cases)
        
        logger.info(f"Retrieved {total_test_cases} test cases from test suite")
        print(f"[TASK] execute_tests_on_device - Retrieved {total_test_cases} test cases")
        
        # Debug: Print all test cases
        for i, suite_case in enumerate(test_cases):
            logger.debug(f"Test case {i+1}: {suite_case.test_case.name} (Type: {suite_case.test_case.test_type})")
            print(f"[DEBUG] execute_tests_on_device - Test case {i+1}: {suite_case.test_case.name} (Type: {suite_case.test_case.test_type})")
        
        # Create TestCaseExecution records for all test cases
        test_execution_ids = []
        device_agent_tests = []
        robot_framework_tests = []
        
        device_data = {
            "device_name": device.name,
            "management_ip": device.management_ip,
            "device_id": device.id,
            "ssh": {
                "host": device.management_ip,
                "username": device_conn.credentials.params.get('username', '') if has_connection else '',
                "password": device_conn.credentials.params.get('password', '') if has_connection else ''
            }
        }
        
        test_suite_data = {
            "test_suite_name": test_suite_execution.test_suite.name,
            "test_suite_id": test_suite_execution.test_suite.id,
            "test_suite_category": test_suite_execution.test_suite.category.name,
            "test_cases": []
        }
        
        for suite_case in test_cases:
            test_case = suite_case.test_case
            
            # Create execution records for Device Agent type tests (type=2)
            if test_case.test_type == 2:
                logger.info(f"Creating execution record for device agent test: {test_case.name}")
                print(f"[TASK] execute_tests_on_device - Creating execution record for: {test_case.name}")
                
                if has_connection:
                    # Normal execution record for devices with connection
                    test_execution = TestCaseExecution.objects.create(
                        test_suite_execution=test_suite_execution,
                        device=device,
                        test_case=test_case,
                        status=TestExecutionStatus.PENDING,
                    )
                    test_execution.save()
                    test_execution_ids.append(test_execution.id)
                else:
                    # Create failed execution record for devices without connection
                    test_execution = TestCaseExecution.objects.create(
                        test_suite_execution=test_suite_execution,
                        device=device,
                        test_case=test_case,
                        status=TestExecutionStatus.FAILED,
                        started_at=timezone.now(),
                        completed_at=timezone.now(),
                        exit_code=1,
                        stdout="No working connection found for device",
                        error_message="No working connection found for device"
                    )
                    test_execution.save()
                
                if test_execution and test_execution.id:
                    print(f"✅ Successfully created TestCaseExecution with ID: {test_execution.id}")
                
                logger.debug(f"Created TestCaseExecution ID: {test_execution.id}")
                print(f"[DEBUG] execute_tests_on_device - Created TestCaseExecution ID: {test_execution.id}")
                
            else:  # Robot Framework tests
                test_execution = TestCaseExecution.objects.create(
                    test_suite_execution=test_suite_execution,
                    device=device,
                    test_case=test_case,
                    status=TestExecutionStatus.PENDING,
                )
                test_execution.save()
                robot_framework_tests.append(test_execution.id)
                test_suite_data["test_cases"].append({
                    "test_case_id": test_case.test_case_id,
                    "test_case_name": test_case.name,
                    "params": test_case.params,
                    "execution_id": test_execution.id
                })
                logger.info(f"Created execution record for Robot Framework test: {test_case.name}")
                print(f"[TASK] Created Robot Framework test execution ID: {test_execution.id}")
        
        logger.info(f"Created {len(test_execution_ids)} device agent test execution records out of {total_test_cases} total tests")
        print(f"[TASK] execute_tests_on_device - Created {len(test_execution_ids)} device agent tests out of {total_test_cases} total")
        
        # Only proceed with execution if device has connection
        if has_connection:
            logger.info(f"Created {len(robot_framework_tests)} Robot Framework and {len(device_agent_tests)} Device Agent test execution records")
            
            if robot_framework_tests:
                logger.info(f"Sending {len(robot_framework_tests)} Robot Framework tests to API")
                print(f"[TASK] Sending {len(robot_framework_tests)} Robot Framework tests to external API")
                
                execute_robot_framework_tests.delay(
                    robot_framework_tests,
                    device_data,
                    test_suite_data,
                )
            
            # Launch device agent test cases in parallel
            if test_execution_ids:
                logger.info(f"Launching {len(test_execution_ids)} test cases in parallel")
                print(f"[TASK] execute_tests_on_device - Launching {len(test_execution_ids)} tests in parallel")
                
                for test_execution_id in test_execution_ids:
                    logger.debug(f"Queuing test execution ID: {test_execution_id}")
                    print(f"[DEBUG] execute_tests_on_device - Queuing test execution ID: {test_execution_id}")
                    print(f"✅✅ Successfully created TestCaseExecution with ID: {test_execution_id}")
                    
                    execute_single_test_case.delay(
                        test_execution_id,
                        device_conn.credentials.params,
                        device.management_ip,
                        device_execution_id
                    )
                
                logger.info(f"Successfully queued all {len(test_execution_ids)} test cases")
                print(f"[TASK] execute_tests_on_device - Successfully queued all test cases")
            else:
                logger.warning("No device agent tests found to execute")
                print(f"[WARNING] execute_tests_on_device - No device agent tests found")
        else:
            logger.info("Device has no connection, all tests marked as failed")
            print(f"[TASK] execute_tests_on_device - Device has no connection, all tests marked as failed")
        
        # Start completion checking
        logger.info("Starting completion checking process")
        print(f"[TASK] execute_tests_on_device - Starting completion checking")
        check_device_execution_completion.delay(device_execution_id)
        
    except TestSuiteExecutionDevice.DoesNotExist:
        error_msg = f"Device execution with ID {device_execution_id} not found"
        logger.error(error_msg)
        print(f"[ERROR] execute_tests_on_device - {error_msg}")
        
    except Exception as e:
        error_msg = f"Error setting up tests on device: {str(e)}"
        logger.error(error_msg, exc_info=True)
        print(f"[ERROR] execute_tests_on_device - {error_msg}")
        
        try:
            device_execution.status = 'failed'
            device_execution.output = f"Setup error: {str(e)}"
            device_execution.completed_at = timezone.now()
            device_execution.save()
            logger.info("Updated device execution status to 'failed'")
            print(f"[TASK] execute_tests_on_device - Updated status to 'failed'")
        except:
            logger.error("Failed to update device execution status")
            print(f"[ERROR] execute_tests_on_device - Failed to update status")

@shared_task
def execute_single_test_case(test_execution_id, ssh_params, device_ip, device_execution_id):
    """
    Execute a single test case on a device via SSH or NB_API based on DEVICE_EXECUTION_TYPE.
    """
    print(f"✅✅✅  Successfully created TestCaseExecution with ID: {test_execution_id}")
    
    # Route to appropriate execution method based on DEVICE_EXECUTION_TYPE
    if DEVICE_EXECUTION_TYPE == 1:
        # SSH execution
        execute_test_via_ssh(test_execution_id, ssh_params, device_ip, device_execution_id)
    elif DEVICE_EXECUTION_TYPE == 2:
        # NB_API execution
        execute_test_via_nb_api(test_execution_id, ssh_params, device_ip, device_execution_id)
    else:
        logger.error(f"Invalid DEVICE_EXECUTION_TYPE: {DEVICE_EXECUTION_TYPE}. Must be 1 (SSH) or 2 (NB_API)")
        print(f"[ERROR] Invalid DEVICE_EXECUTION_TYPE: {DEVICE_EXECUTION_TYPE}")


def execute_test_via_ssh(test_execution_id, ssh_params, device_ip, device_execution_id):
    """
    Execute a test case via SSH connection.
    This is the original SSH-based execution logic.
    """
    try:
        # Retrieve the test execution record
        test_execution = TestCaseExecution.objects.get(pk=test_execution_id)
        test_case = test_execution.test_case
        
        logger.info(f"Retrieved test execution: {test_execution}")
        logger.info(f"Test case: {test_case.name} (ID: {test_case.test_case_id})")
        print(f"[TASK] execute_test_via_ssh - Test case: {test_case.name} (ID: {test_case.test_case_id})")
        print(f"[TASK] execute_test_via_ssh - Device: {test_execution.device.name}")
        
        # Update status to running
        test_execution.status = TestExecutionStatus.RUNNING
        test_execution.started_at = timezone.now()
        test_execution.save()
        
        logger.info(f"Updated test execution status to 'running' at {test_execution.started_at}")
        print(f"[TASK] execute_test_via_ssh - Updated status to 'running' at {test_execution.started_at}")
        
        # Create SSH connection for this specific test
        logger.info(f"Creating SSH connection to {device_ip}")
        print(f"[TASK] execute_test_via_ssh - Creating SSH connection to {device_ip}")
        
        ssh_conn = Ssh(ssh_params, [device_ip])
        
        try:
            # Establish SSH connection
            logger.info("Attempting to connect via SSH")
            print(f"[TASK] execute_test_via_ssh - Attempting SSH connection")
            
            ssh_conn.connect()
            
            logger.info("SSH connection established successfully")
            print(f"[TASK] execute_test_via_ssh - SSH connection established")
            
            # Prepare test execution command
            test_path = f"/usr/bin/tests/Test_Cases/{test_case.test_case_id}/{test_case.test_case_id}.py"
            print("✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅")
            print(test_path)
            print("✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅")

            command = f"python3 {test_path}"
            
            logger.info(f"Executing test script: {command}")
            print(f"[TASK] execute_test_via_ssh - Executing command: {command}")
            
            # Execute the test with timeout
            logger.info(f"Starting test execution for {test_case.test_case_id} on {device_ip}")
            print(f"[TASK] execute_test_via_ssh - Starting test execution")
            
            output, exit_code = ssh_conn.exec_command(
                command,
                timeout=86400,  # 1 day (24 hours) max per test
                exit_codes=[0, 1, 2, 3, 4, 5],  # Accept multiple exit codes
                raise_unexpected_exit=False
            )
            
            logger.info(f"Test execution completed with exit code: {exit_code}")
            print(f"[TASK] execute_test_via_ssh - Test completed with exit code: {exit_code}")
            print(f"[TASK] execute_test_via_ssh - Output length: {len(output) if output else 0} characters")
            
            # Log output for debugging (truncated)
            if output:
                output_preview = output[:200] + "..." if len(output) > 200 else output
                logger.debug(f"Test output preview: {output_preview}")
                print(f"[DEBUG] execute_test_via_ssh - Output preview: {output_preview}")
            
            # Save results to database
            test_execution.stdout = output
            test_execution.exit_code = exit_code
            test_execution.completed_at = timezone.now()
            
            # Determine test status based on exit code
            if exit_code == 0:
                test_execution.status = TestExecutionStatus.SUCCESS
                logger.info(f"Test {test_case.test_case_id} PASSED")
                print(f"[TASK] execute_test_via_ssh - Test {test_case.test_case_id} PASSED")
            else:
                test_execution.status = TestExecutionStatus.FAILED
                logger.info(f"Test {test_case.test_case_id} FAILED with exit code {exit_code}")
                print(f"[TASK] execute_test_via_ssh - Test {test_case.test_case_id} FAILED with exit code {exit_code}")
                
            test_execution.save()
            
            logger.info(f"Test execution results saved to database")
            print(f"[TASK] execute_test_via_ssh - Results saved to database")
            
        except Exception as e:
            error_msg = f"Error executing test {test_case.test_case_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            print(f"[ERROR] execute_test_via_ssh - {error_msg}")
            
            # Update test execution with error
            test_execution.status = TestExecutionStatus.FAILED
            test_execution.error_message = str(e)
            test_execution.completed_at = timezone.now()
            test_execution.save()
            
            logger.info("Updated test execution with error status")
            print(f"[TASK] execute_test_via_ssh - Updated with error status")
            
        finally:
            # Always disconnect SSH connection
            try:
                logger.info("Disconnecting SSH connection")
                print(f"[TASK] execute_test_via_ssh - Disconnecting SSH")
                ssh_conn.disconnect()
                logger.info("SSH connection disconnected")
                print(f"[TASK] execute_test_via_ssh - SSH disconnected")
            except Exception as disconnect_error:
                logger.warning(f"Error disconnecting SSH: {disconnect_error}")
                print(f"[WARNING] execute_test_via_ssh - Error disconnecting SSH: {disconnect_error}")
        
        # Check if all tests are done for this device
        logger.info("Triggering device completion check")
        print(f"[TASK] execute_test_via_ssh - Triggering completion check")
        check_device_execution_completion.delay(device_execution_id)
        
    except TestCaseExecution.DoesNotExist:
        error_msg = f"Test execution with ID {test_execution_id} not found"
        logger.error(error_msg)
        print(f"[ERROR] execute_test_via_ssh - {error_msg}")
        
    except Exception as e:
        error_msg = f"Error in SSH test execution: {str(e)}"
        logger.error(error_msg, exc_info=True)
        print(f"[ERROR] execute_test_via_ssh - {error_msg}")


def execute_test_via_nb_api(test_execution_id, ssh_params, device_ip, device_execution_id):
    """
    Execute a test case via NB_API.
    Makes GET request to device's CGI endpoint and waits for completion.
    """
    try:
        # Retrieve the test execution record
        test_execution = TestCaseExecution.objects.get(pk=test_execution_id)
        test_case = test_execution.test_case
        
        logger.info(f"Retrieved test execution for NB_API: {test_execution}")
        logger.info(f"Test case: {test_case.name} (ID: {test_case.test_case_id})")
        print(f"[TASK] execute_test_via_nb_api - Test case: {test_case.name} (ID: {test_case.test_case_id})")
        print(f"[TASK] execute_test_via_nb_api - Device: {test_execution.device.name}")
        
        # Update status to running
        test_execution.status = TestExecutionStatus.RUNNING
        test_execution.started_at = timezone.now()
        test_execution.save()
        
        logger.info(f"Updated test execution status to 'running' at {test_execution.started_at}")
        print(f"[TASK] execute_test_via_nb_api - Updated status to 'running'")
        
        # Construct API URL
        api_url = f"http://{device_ip}/cgi-bin/test_script.py?test_id={test_case.test_case_id}&execution_id={test_execution_id}"


        try:
             print(f"🔄 [DEBUG] Checking if API is reachable...")
             base_url = api_url.rsplit('/', 2)[0]  # Get base URL
            #  test_response = requests.get(base_url, timeout=60)
             print(f"✅✅✅✅✅✅✅✅✅✅✅✅         ✅✅✅✅✅✅✅✅✅✅✅✅ [DEBUG] API server is reachable at {base_url}")
        except Exception as e:
             print(f"❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌ [ERROR] Cannot reach API server: {e}")
             print(f"⚠️  [ERROR] Make sure the server at {api_url} is running")
         # curl "http://10.10.10.20/cgi-bin/test_script.py?test_id=TestCase_001&execution_id=1001"

        logger.info(f"NB_API URL: {api_url}")
        print(f"[TASK] execute_test_via_nb_api - Calling API: {api_url}")
        
        try:
            # Make GET request with no timeout (wait indefinitely)
            # This ensures requests are processed sequentially on resource-limited devices
            logger.info(f"Starting NB_API request for test {test_case.test_case_id}")
            print(f"[TASK] execute_test_via_nb_api - Sending GET request (no timeout)")
            
            response = requests.get(
                api_url,
                timeout=None,  # No timeout - wait indefinitely
                allow_redirects=True
            )
            
            logger.info(f"NB_API response received. Status code: {response.status_code}")
            print(f"[TASK] execute_test_via_nb_api - Response status: {response.status_code}")
            
            # Process response
            # test_execution.stdout = response.text
            # test_execution.completed_at = timezone.now()
            
            # Determine success based on HTTP status code
            # if response.status_code == 200:
            #     test_execution.status = TestExecutionStatus.SUCCESS
            #     test_execution.exit_code = 0
            #     logger.info(f"Test {test_case.test_case_id} PASSED via NB_API")
            #     print(f"[TASK] execute_test_via_nb_api - Test PASSED")
            # else:
            #     test_execution.status = TestExecutionStatus.FAILED
            #     test_execution.exit_code = response.status_code
            #     test_execution.error_message = f"HTTP {response.status_code}: {response.reason}"
            #     logger.warning(f"Test {test_case.test_case_id} FAILED with HTTP {response.status_code}")
            #     print(f"[TASK] execute_test_via_nb_api - Test FAILED with HTTP {response.status_code}")
            
            # Log response details
            if response.text:
                output_preview = response.text[:200] + "..." if len(response.text) > 200 else response.text
                logger.debug(f"Response preview: {output_preview}")
                print(f"[DEBUG] execute_test_via_nb_api - Response preview: {output_preview}")
            
            # test_execution.save()
            logger.info("Test execution results saved to database")
            print(f"[TASK] execute_test_via_nb_api - Results saved")
            
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Failed to connect to device at {device_ip}: {str(e)}"
            logger.error(error_msg)
            print(f"[ERROR] execute_test_via_nb_api - Connection error: {error_msg}")
            
            test_execution.status = TestExecutionStatus.FAILED
            test_execution.error_message = error_msg
            test_execution.stdout = "Connection failed - device unreachable"
            test_execution.exit_code = -1
            test_execution.completed_at = timezone.now()
            test_execution.save()
            
        except requests.exceptions.Timeout as e:
            # This shouldn't happen with timeout=None, but handle it anyway
            error_msg = f"Request timed out for test {test_case.test_case_id}: {str(e)}"
            logger.error(error_msg)
            print(f"[ERROR] execute_test_via_nb_api - Timeout: {error_msg}")
            
            # test_execution.status = TestExecutionStatus.TIMEOUT
            test_execution.status = TestExecutionStatus.FAILED
            test_execution.error_message = error_msg
            test_execution.stdout = "Request timed out"
            test_execution.exit_code = -2
            test_execution.completed_at = timezone.now()
            test_execution.save()
            
        except requests.exceptions.RequestException as e:
            # Catch all other requests exceptions
            error_msg = f"HTTP request failed for test {test_case.test_case_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            print(f"[ERROR] execute_test_via_nb_api - Request error: {error_msg}")
            
            test_execution.status = TestExecutionStatus.FAILED
            test_execution.error_message = error_msg
            test_execution.stdout = f"HTTP request error: {type(e).__name__}"
            test_execution.exit_code = -3
            test_execution.completed_at = timezone.now()
            test_execution.save()
            
        except Exception as e:
            # Catch any other unexpected errors
            error_msg = f"Unexpected error during NB_API execution: {str(e)}"
            logger.error(error_msg, exc_info=True)
            print(f"[ERROR] execute_test_via_nb_api - Unexpected error: {error_msg}")
            
            test_execution.status = TestExecutionStatus.FAILED
            test_execution.error_message = error_msg
            test_execution.stdout = "Unexpected error occurred"
            test_execution.exit_code = -4
            test_execution.completed_at = timezone.now()
            test_execution.save()
        
        # Check if all tests are done for this device
        logger.info("Triggering device completion check")
        print(f"[TASK] execute_test_via_nb_api - Triggering completion check")
        check_device_execution_completion.delay(device_execution_id)
        
    except TestCaseExecution.DoesNotExist:
        error_msg = f"Test execution with ID {test_execution_id} not found"
        logger.error(error_msg)
        print(f"[ERROR] execute_test_via_nb_api - {error_msg}")
        
    except Exception as e:
        error_msg = f"Error in NB_API test execution setup: {str(e)}"
        logger.error(error_msg, exc_info=True)
        print(f"[ERROR] execute_test_via_nb_api - {error_msg}")

@shared_task
def check_device_execution_completion(device_execution_id, retry_count=0):
    """
    Check if all tests are completed for a device and update its status.
    
    This task:
    1. Counts pending/running tests for the device
    2. If tests are still running, schedules a retry
    3. If all tests are complete, generates a summary report
    4. Updates device execution status and output
    5. Triggers suite-level completion checking
    
    Args:
        device_execution_id (int): Primary key of the TestSuiteExecutionDevice record
        retry_count (int): Number of times this check has been retried
        
    Returns:
        None
        
    Side Effects:
        - Updates device execution status and output
        - Schedules retry if tests are still running
        - Triggers suite completion checking when device is done
    """
    # max_retries = 600  # Max 50 minutes of checking (600 * 5 seconds)
    max_retries = 1440  # Max 24 hours of checking (1440 * 60 seconds)

    
    logger.info(f"Checking device execution completion for ID: {device_execution_id} (retry: {retry_count})")
    print(f"[TASK] check_device_execution_completion - Device execution ID: {device_execution_id}, retry: {retry_count}")
    
    try:
        # Retrieve device execution record
        device_execution = TestSuiteExecutionDevice.objects.get(pk=device_execution_id)
        test_suite_execution = device_execution.test_suite_execution
        
        logger.info(f"Retrieved device execution for device: {device_execution.device.name}")
        print(f"[TASK] check_device_execution_completion - Device: {device_execution.device.name}")
        
        # Count pending/running tests for this device
        # pending_or_running = TestCaseExecution.objects.filter(
        #     test_suite_execution=test_suite_execution,
        #     device=device_execution.device,
        #     status__in=[TestExecutionStatus.PENDING, TestExecutionStatus.RUNNING],
        # ).count()

        pending_or_running = TestCaseExecution.objects.filter(
            test_suite_execution=test_suite_execution,
            device=device_execution.device,
            status__in=[TestExecutionStatus.PENDING, TestExecutionStatus.RUNNING],
            test_case__test_type=2  # Only count Device Agent tests
        ).count()
        
        logger.info(f"Found {pending_or_running} tests still pending/running")
        print(f"[TASK] check_device_execution_completion - {pending_or_running} tests still pending/running")
        
        if pending_or_running > 0:
            # Not all tests completed, check again later
            if retry_count < max_retries:
                logger.info(f"Tests still running, scheduling retry {retry_count + 1}/{max_retries} in 5 seconds")
                print(f"[TASK] check_device_execution_completion - Scheduling retry {retry_count + 1}/{max_retries}")
                
                check_device_execution_completion.apply_async(
                    args=[device_execution_id, retry_count + 1],
                    # countdown=5  # Check again in 5 seconds
                    countdown=3600  # Check again in 1 hour (3600 seconds)

                )
                return
            else:
                logger.error(f"Max retries ({max_retries}) exceeded for device execution {device_execution_id}")
                print(f"[ERROR] check_device_execution_completion - Max retries exceeded")
                
                # Force completion due to timeout
                device_execution.status = 'failed'
                device_execution.output = f"Timeout: Some tests did not complete within expected time"
                device_execution.completed_at = timezone.now()
                device_execution.save()
                return
        
        # All tests completed, generate summary report
        logger.info(f"All tests completed for device {device_execution.device.name}")
        print(f"[TASK] check_device_execution_completion - All tests completed for {device_execution.device.name}")
        
        # Get all test executions for this device
        # test_executions = TestCaseExecution.objects.filter(
        #     test_suite_execution=test_suite_execution,
        #     device=device_execution.device
        # ).order_by('test_case__name')  # Order by name since we're not using execution_order
        # With this:
        test_executions = TestCaseExecution.objects.filter(
            test_suite_execution=test_suite_execution,
            device=device_execution.device,
            test_case__test_type=2  # Only get Device Agent test results
        ).order_by('test_case__name')
        
        total_executions = test_executions.count()
        logger.info(f"Retrieved {total_executions} test executions for summary")
        print(f"[TASK] check_device_execution_completion - Retrieved {total_executions} test executions")
        
        # Build summary report
        output_lines = []
        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        
        output_lines.append(f"Test Execution Summary for {device_execution.device.name}")
        output_lines.append("=" * 60)
        
        # Process each test execution
        for test_exec in test_executions:
            total_tests += 1
            duration = ""
            
            # Calculate duration
            if test_exec.execution_duration:
                duration = f" ({test_exec.formatted_duration})"
            elif test_exec.started_at and test_exec.completed_at:
                duration_delta = test_exec.completed_at - test_exec.started_at
                duration = f" ({int(duration_delta.total_seconds())}s)"
            
            # Process based on status
            if test_exec.status == TestExecutionStatus.SUCCESS:
                passed_tests += 1
                output_lines.append(f"✓ {test_exec.test_case.name}: PASSED{duration}")
                
                logger.debug(f"Test PASSED: {test_exec.test_case.name}")
                print(f"[DEBUG] check_device_execution_completion - PASSED: {test_exec.test_case.name}")

                print(f"🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️: {test_exec.stdout}")

                
                
                if test_exec.stdout and test_exec.stdout.strip():
                    output_lines.append(f"   Output: {test_exec.stdout.strip()[:100]}...")
                    
            else:
                failed_tests += 1
                output_lines.append(f"✗ {test_exec.test_case.name}: FAILED{duration}")
                
                logger.debug(f"Test FAILED: {test_exec.test_case.name}")
                print(f"[DEBUG] check_device_execution_completion - FAILED: {test_exec.test_case.name}")
                
                if test_exec.error_message:
                    output_lines.append(f"   Error: {test_exec.error_message}")
                    
                if test_exec.stdout and test_exec.stdout.strip():
                    output_lines.append(f"   Output: {test_exec.stdout.strip()[:100]}...")
        
        # Add summary statistics
        output_lines.append("=" * 60)
        output_lines.append(f"Total: {total_tests} | Passed: {passed_tests} | Failed: {failed_tests}")
        
        logger.info(f"Test summary - Total: {total_tests}, Passed: {passed_tests}, Failed: {failed_tests}")
        print(f"[TASK] check_device_execution_completion - Summary: {total_tests} total, {passed_tests} passed, {failed_tests} failed")
        
        # Update device execution status
        device_execution.status = 'completed' if failed_tests == 0 else 'failed'
        device_execution.output = "\n".join(output_lines)
        device_execution.completed_at = timezone.now()
        device_execution.save()
        
        logger.info(f"Updated device execution status to '{device_execution.status}'")
        print(f"[TASK] check_device_execution_completion - Updated status to '{device_execution.status}'")
        
        # Check if all devices in the suite are done
        logger.info("Triggering suite completion check")
        print(f"[TASK] check_device_execution_completion - Triggering suite completion check")
        check_suite_execution_completion.delay(test_suite_execution.id)
        
    except TestSuiteExecutionDevice.DoesNotExist:
        error_msg = f"Device execution with ID {device_execution_id} not found"
        logger.error(error_msg)
        print(f"[ERROR] check_device_execution_completion - {error_msg}")
        
    except Exception as e:
        error_msg = f"Error checking device completion: {str(e)}"
        logger.error(error_msg, exc_info=True)
        print(f"[ERROR] check_device_execution_completion - {error_msg}")




@shared_task
def check_suite_execution_completion(suite_execution_id):
    """
    Check if all devices have completed execution for a test suite.
    
    This task:
    1. Counts devices still in pending/running state
    2. If all devices are complete, logs completion and can trigger notifications
    3. Provides a central point for suite-level completion handling
    
    Args:
        suite_execution_id (int): Primary key of the TestSuiteExecution record
        
    Returns:
        None
        
    Side Effects:
        - Logs completion status
        - Can be extended to send notifications, generate reports, etc.
    """
    logger.info(f"Checking suite execution completion for ID: {suite_execution_id}")
    print(f"[TASK] check_suite_execution_completion - Suite execution ID: {suite_execution_id}")
    
    try:
        # Retrieve suite execution record
        suite_execution = TestSuiteExecution.objects.get(pk=suite_execution_id)
        logger.info(f"Retrieved suite execution: {suite_execution.test_suite.name}")
        print(f"[TASK] check_suite_execution_completion - Suite: {suite_execution.test_suite.name}")
        
        # Count devices still running
        total_devices = TestSuiteExecutionDevice.objects.filter(
            test_suite_execution_id=suite_execution_id
        ).count()
        
        pending_devices = TestSuiteExecutionDevice.objects.filter(
            test_suite_execution_id=suite_execution_id,
            status__in=['pending', 'running']
        ).count()
        
        completed_devices = total_devices - pending_devices
        
        logger.info(f"Suite progress: {completed_devices}/{total_devices} devices completed")
        print(f"[TASK] check_suite_execution_completion - Progress: {completed_devices}/{total_devices} devices completed")
        
        if pending_devices == 0:
            logger.info(f"Test suite execution {suite_execution_id} completed on all devices")
            print(f"[TASK] check_suite_execution_completion - All devices completed!")
            
            # Get completion statistics
            completed_device_executions = TestSuiteExecutionDevice.objects.filter(
                test_suite_execution_id=suite_execution_id,
                status='completed'
            ).count()
            
            failed_device_executions = TestSuiteExecutionDevice.objects.filter(
                test_suite_execution_id=suite_execution_id,
                status='failed'
            ).count()
            
            logger.info(f"Suite completion stats - Completed: {completed_device_executions}, Failed: {failed_device_executions}")
            print(f"[TASK] check_suite_execution_completion - Stats: {completed_device_executions} completed, {failed_device_executions} failed")
            
            # Here you could send notifications, generate reports, etc.
            # For example:
            # send_suite_completion_notification.delay(suite_execution_id)
            # generate_suite_report.delay(suite_execution_id)
            
        else:
            logger.info(f"Suite execution still in progress: {pending_devices} devices pending")
            print(f"[TASK] check_suite_execution_completion - Still in progress: {pending_devices} devices pending")
            
    except TestSuiteExecution.DoesNotExist:
        error_msg = f"Test suite execution with ID {suite_execution_id} not found"
        logger.error(error_msg)
        print(f"[ERROR] check_suite_execution_completion - {error_msg}")
        
    except Exception as e:
        error_msg = f"Error checking suite completion: {str(e)}"
        logger.error(error_msg, exc_info=True)
        print(f"[ERROR] check_suite_execution_completion - {error_msg}")


# Additional helper task for debugging

@shared_task
def execute_robot_framework_tests(test_execution_ids, device_data, test_suite_data):
    """
    Execute Robot Framework tests by calling external Robot Framework API.
    This is completely separate from device agent tests.
    """
    print(f"\n{'='*80}")
    print(f"[DEBUG] ROBOT FRAMEWORK TEST EXECUTION STARTED")
    print(f"{'='*80}")
    
    logger.info(f"Executing Robot Framework tests for {len(test_execution_ids)} test cases")
    
    # Convert UUIDs to strings
    test_execution_ids_str = [str(id) for id in test_execution_ids]
    
    # Fix device_data UUIDs
    device_data_fixed = {
        "device_name": device_data.get('device_name', 'N/A'),
        "management_ip": device_data.get('management_ip', 'N/A'),
        "device_id": str(device_data.get('device_id', '')),  # Convert UUID to string
        "ssh": device_data.get('ssh', {})
    }
    
    # Fix test_suite_data UUIDs
    test_suite_data_fixed = {
        "test_suite_name": test_suite_data.get('test_suite_name', 'N/A'),
        "test_suite_id": str(test_suite_data.get('test_suite_id', '')),  # Convert UUID to string
        "test_suite_category": test_suite_data.get('test_suite_category', 'N/A'),
        "test_cases": []
    }
    
    # Fix test case execution IDs
    for test_case in test_suite_data.get('test_cases', []):
        print(">>>>>>>>>>>>>>>>>>>>test_case" ,test_case)
        test_suite_data_fixed["test_cases"].append({
            "test_case_id": test_case.get('test_case_id', 'N/A'),
            "test_case_name": test_case.get('test_case_name', 'N/A'),
            "execution_id": str(test_case.get('execution_id', '')), # Convert UUID to string
            "params": test_case.get('params', 'N/A'),

            
        })
    
    # Extract and convert device_execution_id
    device_execution_id = str(test_suite_data.get("device_execution_id", ''))
    
    # Debug: Print input parameters
    print(f"\n[DEBUG] Input Parameters (after UUID conversion):")
    print(f"[DEBUG] Number of test executions: {len(test_execution_ids_str)}")
    print(f"[DEBUG] Test execution IDs: {test_execution_ids_str}")
    
    print(f"\n[DEBUG] Device Data:")
    print(f"  - Device Name: {device_data_fixed.get('device_name', 'N/A')}")
    print(f"  - Device ID: {device_data_fixed.get('device_id', 'N/A')}")
    print(f"  - Device IP: {device_data_fixed.get('management_ip', 'N/A')}")
    print(f"  - SSH Host: {device_data_fixed.get('ssh', {}).get('host', 'N/A')}")
    print(f"  - SSH Username: {device_data_fixed.get('ssh', {}).get('username', 'N/A')}")
    print(f"  - SSH Password: {'***' if device_data_fixed.get('ssh', {}).get('password') else 'N/A'}")
    
    print(f"\n[DEBUG] Test Suite Data:")
    print(f"  - Suite Name: {test_suite_data_fixed.get('test_suite_name', 'N/A')}")
    print(f"  - Suite ID: {test_suite_data_fixed.get('test_suite_id', 'N/A')}")
    print(f"  - Suite Category: {test_suite_data_fixed.get('test_suite_category', 'N/A')}")
    print(f"  - Device Execution ID: {device_execution_id}")
    print(f"  - Number of test cases: {len(test_suite_data_fixed.get('test_cases', []))}")
    
    print(f"\n[DEBUG] Test Cases to Execute:")
    for idx, test_case in enumerate(test_suite_data_fixed.get('test_cases', []), 1):
        print(f"  {idx}. Test Case ID: {test_case.get('test_case_id', 'N/A')}")
        print(f"     Test Case Name: {test_case.get('test_case_name', 'N/A')}")
        print(f"     Execution ID: {test_case.get('execution_id', 'N/A')}")
    
    # Prepare API payload with string UUIDs
    api_payload = {
        "devices": [device_data_fixed],  # API expects array of devices
        "test_suites": {
            "test_suite_name": test_suite_data_fixed.get('test_suite_name'),
            "test_suite_id": test_suite_data_fixed.get('test_suite_id'),
            "test_suite_category": test_suite_data_fixed.get('test_suite_category'),
            "test_cases": test_suite_data_fixed.get('test_cases', [])
        },
        "execution_metadata": {
            "device_execution_id": device_execution_id,
            "test_execution_ids": test_execution_ids_str
        }
    }
    
    print(f"\n[DEBUG] API Payload:")
    # print(f"[DEBUG] Full payload: {json.dumps(api_payload, indent=2)}")
    
    # Call Robot Framework API
    # robot_api_url = "http://0.0.0.0:8080/run-robot/"
    # robot_api_url = "http://10.8.12.123:8080/run-robot/"
    robot_api_url = " http://192.168.122.1:8080/api/v1/run-robot/" # sachin
    # robot_api_url = "http://192.168.201.37:8080/run-robot/" # kalyani



    # robot_api_url = "http://192.168.201.37:8080/run-robot/"
    print(f"\n🔍 [DEBUG] Making API Call:")
    print(f"📍 [DEBUG] API URL: {robot_api_url}")
    print(f"📮 [DEBUG] Method: POST")
    print(f"⏱️  [DEBUG] Timeout: 6000 seconds")
    # Check if API is reachable first


    
    try:
     print(f"🔄 [DEBUG] Checking if API is reachable...")
     base_url = robot_api_url.rsplit('/', 2)[0]  # Get base URL
     test_response = requests.get(base_url, timeout=60)
     print(f"✅✅✅✅✅✅✅✅✅✅✅✅         ✅✅✅✅✅✅✅✅✅✅✅✅ [DEBUG] API server is reachable at {base_url}")
    except Exception as e:
     print(f"❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌ [ERROR] Cannot reach API server: {e}")
     print(f"⚠️  [ERROR] Make sure the server at {robot_api_url} is running")




    
    try:
        print(f"[DEBUG] Sending request to Robot Framework API...")
        
        response = requests.post(
            robot_api_url,
            json=api_payload,
            timeout=6000  # Quick timeout just to submit the job
        )
        
        print(f"\n[DEBUG] API Response:")
        print(f"[DEBUG] Status Code: {response.status_code}")
        print(f"[DEBUG] Response Headers: {dict(response.headers)}")
        
        try:
            response_json = response.json()
            # print(f"[DEBUG] Response Body: {json.dumps(response_json, indent=2)}")
        except:
            print(f"[DEBUG] Response Body (text): {response.text[:500]}...")  # First 500 chars
        
        if response.status_code == 200:
            logger.info("Robot Framework API called successfully")
            print(f"\n[DEBUG] ✅ API call successful! Updating test execution statuses...")
            
            # Update test execution records to running
            for idx, exec_id in enumerate(test_execution_ids, 1):
                try:
                    print(f"[DEBUG] Updating test execution {idx}/{len(test_execution_ids)} (ID: {exec_id})...")
                    
                    test_exec = TestCaseExecution.objects.get(pk=exec_id)
                    old_status = test_exec.status
                    
                    test_exec.status = TestExecutionStatus.RUNNING
                    test_exec.started_at = timezone.now()
                    test_exec.save()
                    
                    print(f"[DEBUG] ✅ Updated test execution {exec_id}: {old_status} -> {TestExecutionStatus.RUNNING}")
                    
                except TestCaseExecution.DoesNotExist:
                    print(f"[DEBUG] ❌ Test execution {exec_id} not found in database!")
                    logger.error(f"Test execution {exec_id} not found")
                    
                except Exception as e:
                    print(f"[DEBUG] ❌ Error updating test execution {exec_id}: {str(e)}")
                    logger.error(f"Error updating test execution {exec_id}: {str(e)}")
                    
        else:
            logger.error(f"Robot Framework API call failed: {response.status_code}")
            print(f"\n[DEBUG] ❌ API call failed! Status: {response.status_code}")
            print(f"[DEBUG] Marking all tests as failed...")
            
            # Mark tests as failed
            for idx, exec_id in enumerate(test_execution_ids, 1):
                try:
                    print(f"[DEBUG] Failing test execution {idx}/{len(test_execution_ids)} (ID: {exec_id})...")
                    
                    test_exec = TestCaseExecution.objects.get(pk=exec_id)
                    test_exec.status = TestExecutionStatus.FAILED
                    test_exec.error_message = f"Robot Framework API call failed: {response.status_code}"
                    test_exec.completed_at = timezone.now()
                    # test_exec.save()
                    
                    print(f"[DEBUG] ✅ Marked test execution {exec_id} as FAILED")
                    
                except Exception as e:
                    print(f"[DEBUG] ❌ Error updating failed test {exec_id}: {str(e)}")
                    logger.error(f"Error updating failed test {exec_id}: {str(e)}")
                    
    except requests.exceptions.Timeout:
        print(f"\n[DEBUG] ❌ API call timed out!")
        logger.error("Robot Framework API call timed out")
        
        # Mark all tests as failed due to timeout
        for exec_id in test_execution_ids:
            try:
                test_exec = TestCaseExecution.objects.get(pk=exec_id)
                test_exec.status = TestExecutionStatus.FAILED
                test_exec.error_message = "Robot Framework API timeout"
                test_exec.completed_at = timezone.now()
                # test_exec.save()
                print(f"[DEBUG] Marked test {exec_id} as FAILED due to timeout")
            except Exception as e:
                print(f"[DEBUG] Error updating test {exec_id} after timeout: {str(e)}")
                
    except Exception as e:
        print(f"\n[DEBUG] ❌ Unexpected error calling Robot Framework API!")
        print(f"[DEBUG] Error type: {type(e).__name__}")
        print(f"[DEBUG] Error message: {str(e)}")
        print(f"[DEBUG] Traceback:")
        import traceback
        traceback.print_exc()
        
        logger.error(f"Error calling Robot Framework API: {str(e)}")
        
        # Mark all tests as failed due to error
        for exec_id in test_execution_ids:
            try:
                test_exec = TestCaseExecution.objects.get(pk=exec_id)
                test_exec.status = TestExecutionStatus.FAILED
                test_exec.error_message = f"API error: {str(e)}"
                test_exec.completed_at = timezone.now()
                # test_exec.save()
                print(f"[DEBUG] Marked test {exec_id} as FAILED due to error")
            except Exception as update_error:
                print(f"[DEBUG] Error updating test {exec_id} after API error: {str(update_error)}")
    
    print(f"\n[DEBUG] Robot Framework test execution task completed")
    print(f"{'='*80}\n")


@shared_task
def retry_test_execution(test_execution_id):
    """
    Retry a single test execution
    """
    from .swapper import load_model
    TestCaseExecution = load_model("TestCaseExecution")
    TestSuiteExecutionDevice = load_model("TestSuiteExecutionDevice")
    
    try:
        test_execution = TestCaseExecution.objects.get(pk=test_execution_id)
        
        # Get device and device execution info
        device = test_execution.device
        test_suite_execution = test_execution.test_suite_execution
        
        # Find the device execution record
        try:
            device_execution = TestSuiteExecutionDevice.objects.get(
                test_suite_execution=test_suite_execution,
                device=device
            )
            device_execution_id = device_execution.id
        except TestSuiteExecutionDevice.DoesNotExist:
            logger.error(f"Device execution not found for test execution {test_execution_id}")
            return
        
        # Get device connection if exists
        device_conn = None
        ssh_params = {}
        try:
            device_conn = DeviceConnection.objects.get(
                device=device,
                enabled=True
            )
            ssh_params = device_conn.credentials.params
        except DeviceConnection.DoesNotExist:
            logger.warning(f"No working connection found for device {device.name} during retry")
            # Mark as failed if no connection
            test_execution.status = TestExecutionStatus.FAILED
            test_execution.stdout = "No working connection found for device"
            test_execution.error_message = "No working connection found for device"
            test_execution.exit_code = 1
            test_execution.completed_at = timezone.now()
            test_execution.save()
            return
        
        # Reset the test execution status
        test_execution.status = TestExecutionStatus.PENDING  # Changed from 'running' to use proper enum
        test_execution.started_at = None
        test_execution.completed_at = None
        test_execution.stdout = ''
        test_execution.stderr = ''
        test_execution.exit_code = None
        test_execution.error_message = ''
        test_execution.execution_duration = None
        test_execution.retry_count += 1
        test_execution.save()
        
        logger.info(f"Retrying test execution {test_execution_id} (retry #{test_execution.retry_count})")
        print(f"[TASK] retry_test_execution - Retrying test {test_execution_id}, retry count: {test_execution.retry_count}")
        
        # Check if it's a device agent test (type=2) or robot framework test (type=1)
        if test_execution.test_case.test_type == 2:
            # Device agent test - use execute_single_test_case
            logger.info(f"Retrying device agent test: {test_execution.test_case.name}")
            execute_single_test_case.delay(
                test_execution_id,
                ssh_params,
                device.management_ip,
                device_execution_id
            )
        else:
            # Robot framework test - needs different handling
            logger.info(f"Retrying robot framework test: {test_execution.test_case.name}")
            
            # Prepare data for robot framework API
            device_data = {
                "device_name": device.name,
                "management_ip": device.management_ip,
                "device_id": device.id,
                "ssh": {
                    "host": device.management_ip,
                    "username": ssh_params.get('username', ''),
                    "password": ssh_params.get('password', '')
                }
            }
            
            test_suite_data = {
                "test_suite_name": test_suite_execution.test_suite.name,
                "test_suite_id": test_suite_execution.test_suite.id,
                "test_suite_category": test_suite_execution.test_suite.category.name,
                "test_cases": [{
                    "test_case_id": test_execution.test_case.test_case_id,
                    "test_case_name": test_execution.test_case.name,
                    "params": test_execution.test_case.params,
                    "execution_id": test_execution_id
                }]
            }
            
            # Call robot framework execution
            execute_robot_framework_tests.delay(
                [test_execution_id],
                device_data,
                test_suite_data
            )
        
        logger.info(f"Successfully queued retry for test execution {test_execution_id}")
        
    except TestCaseExecution.DoesNotExist:
        logger.error(f"Test execution {test_execution_id} not found")
    except Exception as e:
        logger.error(f"Error retrying test execution {test_execution_id}: {str(e)}")
        print(f"[ERROR] retry_test_execution - Error: {str(e)}")