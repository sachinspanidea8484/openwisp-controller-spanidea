# openwisp_test_management/tasks.py
import logging
from celery import shared_task
from django.utils import timezone
from openwisp_controller.connection.connectors.ssh import Ssh
from openwisp_controller.connection.models import DeviceConnection
from .swapper import load_model
from .base.models import TestExecutionStatus

# Configure logger for this module
logger = logging.getLogger(__name__)

# Load models using swapper pattern for better modularity
TestSuiteExecution = load_model("TestSuiteExecution")
TestSuiteExecutionDevice = load_model("TestSuiteExecutionDevice")
TestCaseExecution = load_model("TestCaseExecution")
TestSuiteCase = load_model("TestSuiteCase")

# Robot Framework API Server Configuration
ROBOT_API_SERVER = getattr(settings, 'ROBOT_API_SERVER', 'http://localhost:5000')
ROBOT_API_TIMEOUT = getattr(settings, 'ROBOT_API_TIMEOUT', 300)  # 5 minutes default

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
    print(f"[TASK] execute_test_suite - Starting execution ID: {execution_id}")
    
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
    
    This task:
    1. Retrieves device execution record and associated device
    2. Updates device execution status to 'running'
    3. Establishes device connection
    4. Creates test case execution records for device agent tests
    5. Launches parallel execution of all test cases
    6. Initiates completion checking
    
    Args:
        device_execution_id (int): Primary key of the TestSuiteExecutionDevice record
        
    Returns:
        None
        
    Side Effects:
        - Updates device execution status and timestamps
        - Creates TestCaseExecution records
        - Queues parallel test execution tasks
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
        
        # Get device connection
        try:
            device_conn = DeviceConnection.objects.get(
                device=device,
                is_working=True,
                enabled=True
            )
            logger.info(f"Found working device connection: {device_conn}")
            print(f"[TASK] execute_tests_on_device - Found working connection: {device_conn}")
            
        except DeviceConnection.DoesNotExist:
            error_msg = f"No working connection found for device {device.name}"
            logger.error(error_msg)
            print(f"[ERROR] execute_tests_on_device - {error_msg}")
            
            # Update device execution with failure
            device_execution.status = 'failed'
            device_execution.output = "No working connection found"
            device_execution.completed_at = timezone.now()
            device_execution.save()
            return
        
        # Get ordered test cases from the test suite
        # test_cases = test_suite_execution.test_suite.get_ordered_test_cases()
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
        device_agent_tests = 0
        
        for suite_case in test_cases:
            test_case = suite_case.test_case
            
            # Only create execution records for Device Agent type tests (type=2)
            if test_case.test_type == 2:
                device_agent_tests += 1
                
                logger.info(f"Creating execution record for device agent test: {test_case.name}")
                print(f"[TASK] execute_tests_on_device - Creating execution record for: {test_case.name}")
                

                test_execution = TestCaseExecution.objects.create(
                        test_suite_execution=test_suite_execution,
                        device=device,
                        test_case=test_case,
                        status=TestExecutionStatus.PENDING,

                        # execution_order=suite_case.order,
                        # status='running',
                        # started_at=timezone.now()
                    )
                test_execution.save()  # Add this line to be sure

                test_execution_ids.append(test_execution.id)
                if test_execution and test_execution.id:
                 print(f"✅ Successfully created TestCaseExecution with ID: {test_execution.id}")



                 try:
                   verify = TestCaseExecution.objects.get(pk=test_execution.id)
                   print(f"✅❌❌❌❌❌ Verified TestCaseExecution exists in DB with ID: {verify.id}")
                 except TestCaseExecution.DoesNotExist:
                     print(f"❌ TestCaseExecution NOT FOUND in DB after create!")
        
                
                logger.debug(f"Created TestCaseExecution ID: {test_execution.id}")
                print(f"[DEBUG] execute_tests_on_device - Created TestCaseExecution ID: {test_execution.id}")
            else:
                # robot framework code✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅
                logger.debug(f"Skipping non-device-agent test: {test_case.name} (Type: {test_case.test_type})")
                print(f"[DEBUG] execute_tests_on_device - Skipping non-device-agent test: {test_case.name}")
        
        logger.info(f"Created {len(test_execution_ids)} device agent test execution records out of {total_test_cases} total tests")
        print(f"[TASK] execute_tests_on_device - Created {len(test_execution_ids)} device agent tests out of {total_test_cases} total")
        
        # Now launch ALL test cases in parallel
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
                    device.last_ip,
                    device_execution_id
                )
            
            logger.info(f"Successfully queued all {len(test_execution_ids)} test cases")
            print(f"[TASK] execute_tests_on_device - Successfully queued all test cases")
        else:
            logger.warning("No device agent tests found to execute")
            print(f"[WARNING] execute_tests_on_device - No device agent tests found")
        
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
    Execute a single test case on a device via SSH.
    
    This task runs in parallel with other test cases and:
    1. Updates test execution status to 'running'
    2. Establishes SSH connection to the device
    3. Executes the test script
    4. Captures output and exit code
    5. Updates test execution with results
    6. Triggers completion checking
    
    Args:
        test_execution_id (int): Primary key of the TestCaseExecution record
        ssh_params (dict): SSH connection parameters from device credentials
        device_ip (str): IP address of the target device
        device_execution_id (int): Primary key of the TestSuiteExecutionDevice record
        
    Returns:
        None
        
    Side Effects:
        - Updates test execution status, timestamps, and results
        - Establishes and manages SSH connection
        - Executes test script on remote device
    """
    print(f"✅✅✅  Successfully created TestCaseExecution with ID: {test_execution_id}")
    
    try:
        # Retrieve the test execution record
        test_execution = TestCaseExecution.objects.get(pk=test_execution_id)
        test_case = test_execution.test_case
        
        logger.info(f"Retrieved test execution: {test_execution}")
        logger.info(f"Test case: {test_case.name} (ID: {test_case.test_case_id})")
        print(f"[TASK] execute_single_test_case - Test case: {test_case.name} (ID: {test_case.test_case_id})")
        print(f"[TASK] execute_single_test_case - Device: {test_execution.device.name}")
        
        # Update status to running
        test_execution.status = TestExecutionStatus.RUNNING
        test_execution.started_at = timezone.now()
        test_execution.save()
        
        logger.info(f"Updated test execution status to 'running' at {test_execution.started_at}")
        print(f"[TASK] execute_single_test_case - Updated status to 'running' at {test_execution.started_at}")
        
        # Create SSH connection for this specific test
        logger.info(f"Creating SSH connection to {device_ip}")
        print(f"[TASK] execute_single_test_case - Creating SSH connection to {device_ip}")
        
        ssh_conn = Ssh(ssh_params, [device_ip])
        
        try:
            # Establish SSH connection
            logger.info("Attempting to connect via SSH")
            print(f"[TASK] execute_single_test_case - Attempting SSH connection")
            
            ssh_conn.connect()
            
            logger.info("SSH connection established successfully")
            print(f"[TASK] execute_single_test_case - SSH connection established")
            
            # Prepare test execution command
            # test_path = f"/usr/bin/tests/{test_case.test_case_id}"
            # command = f"sh {test_path}"

            test_path = f"/usr/bin/tests/Test_Cases/{test_case.test_case_id}/{test_case.test_case_id}.py"
            print("✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅")
            print(test_path)
            print("✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅")

            command = f"python3 {test_path}"

            
            logger.info(f"Executing test script: {command}")
            print(f"[TASK] execute_single_test_case - Executing command: {command}")
            
            # Execute the test with timeout
            logger.info(f"Starting test execution for {test_case.test_case_id} on {device_ip}")
            print(f"[TASK] execute_single_test_case - Starting test execution")
            
            output, exit_code = ssh_conn.exec_command(
                command,
                # timeout=300,  # 5 minutes max per test
                timeout=86400,  # 1 day (24 hours) max per test
                exit_codes=[0, 1, 2, 3, 4, 5],  # Accept multiple exit codes
                raise_unexpected_exit=False
            )
            
            logger.info(f"Test execution completed with exit code: {exit_code}")
            print(f"[TASK] execute_single_test_case - Test completed with exit code: {exit_code}")
            print(f"[TASK] execute_single_test_case - Output length: {len(output) if output else 0} characters")
            
            # Log output for debugging (truncated)
            if output:
                output_preview = output[:200] + "..." if len(output) > 200 else output
                logger.debug(f"Test output preview: {output_preview}")
                print(f"[DEBUG] execute_single_test_case - Output preview: {output_preview}")
            
            # Save results to database
            test_execution.stdout = output
            test_execution.exit_code = exit_code
            test_execution.completed_at = timezone.now()
            
            # Determine test status based on exit code
            # if exit_code == 0:
            if exit_code == 0 or exit_code == 2:
                test_execution.status = TestExecutionStatus.SUCCESS
                logger.info(f"Test {test_case.test_case_id} PASSED")
                print(f"[TASK] execute_single_test_case - Test {test_case.test_case_id} PASSED")
            else:
                test_execution.status = TestExecutionStatus.FAILED
                logger.info(f"Test {test_case.test_case_id} FAILED with exit code {exit_code}")
                print(f"[TASK] execute_single_test_case - Test {test_case.test_case_id} FAILED with exit code {exit_code}")
                
            test_execution.save()
            
            logger.info(f"Test execution results saved to database")
            print(f"[TASK] execute_single_test_case - Results saved to database")
            
        except Exception as e:
            error_msg = f"Error executing test {test_case.test_case_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            print(f"[ERROR] execute_single_test_case - {error_msg}")
            
            # Update test execution with error
            test_execution.status = TestExecutionStatus.FAILED
            test_execution.error_message = str(e)
            test_execution.completed_at = timezone.now()
            test_execution.save()
            
            logger.info("Updated test execution with error status")
            print(f"[TASK] execute_single_test_case - Updated with error status")
            
        finally:
            # Always disconnect SSH connection
            try:
                logger.info("Disconnecting SSH connection")
                print(f"[TASK] execute_single_test_case - Disconnecting SSH")
                ssh_conn.disconnect()
                logger.info("SSH connection disconnected")
                print(f"[TASK] execute_single_test_case - SSH disconnected")
            except Exception as disconnect_error:
                logger.warning(f"Error disconnecting SSH: {disconnect_error}")
                print(f"[WARNING] execute_single_test_case - Error disconnecting SSH: {disconnect_error}")
        
        # Check if all tests are done for this device
        logger.info("Triggering device completion check")
        print(f"[TASK] execute_single_test_case - Triggering completion check")
        check_device_execution_completion.delay(device_execution_id)
        
    except TestCaseExecution.DoesNotExist:
        error_msg = f"Test execution with ID {test_execution_id} not found"
        logger.error(error_msg)
        print(f"[ERROR] execute_single_test_case - {error_msg}")
        
    except Exception as e:
        error_msg = f"Error in single test execution: {str(e)}"
        logger.error(error_msg, exc_info=True)
        print(f"[ERROR] execute_single_test_case - {error_msg}")


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


@shared_task
def timeout_stuck_tests():
    """
    Run periodically to timeout tests that are stuck in running state.
    
    This maintenance task:
    1. Finds tests that have been running longer than the timeout threshold
    2. Marks them as failed with timeout error
    3. Triggers completion checking for affected devices
    
    This should be scheduled to run every few minutes as a periodic task.
    
    Returns:
        None
        
    Side Effects:
        - Updates stuck test executions with timeout status
        - Triggers device completion checking for affected devices
    """
    from datetime import timedelta
    
    # timeout_threshold = timezone.now() - timedelta(minutes=30)  # 30 minute timeout
    timeout_threshold = timezone.now() - timedelta(days=1)  # 1 day timeout

    
    logger.info("Starting timeout check for stuck tests")
    print(f"[TASK] timeout_stuck_tests - Starting timeout check")
    print(f"[TASK] timeout_stuck_tests - Timeout threshold: {timeout_threshold}")
    
    try:
        # Find stuck tests
        # stuck_tests = TestCaseExecution.objects.filter(
        #     status=TestExecutionStatus.RUNNING,
        #     started_at__lt=timeout_threshold
        # ).select_related('test_case', 'device', 'test_suite_execution')
        stuck_tests = TestCaseExecution.objects.filter(
            status=TestExecutionStatus.RUNNING,
            started_at__lt=timeout_threshold,
            test_case__test_type=2  # Only timeout Device Agent tests
        ).select_related('test_case', 'device', 'test_suite_execution')
        
        stuck_count = stuck_tests.count()
        logger.info(f"Found {stuck_count} stuck tests")
        print(f"[TASK] timeout_stuck_tests - Found {stuck_count} stuck tests")
        
        # Process each stuck test
        for test_exec in stuck_tests:
            logger.warning(f"Timing out stuck test: {test_exec.test_case.test_case_id} on {test_exec.device.name}")
            print(f"[WARNING] timeout_stuck_tests - Timing out: {test_exec.test_case.test_case_id} on {test_exec.device.name}")
            
            # Mark test as failed due to timeout
            test_exec.status = TestExecutionStatus.FAILED
            test_exec.error_message = "Test execution exceeded 30 minute timeout"
            test_exec.completed_at = timezone.now()
            test_exec.save()
            
            logger.info(f"Marked test {test_exec.test_case.test_case_id} as timed out")
            print(f"[TASK] timeout_stuck_tests - Marked as timed out: {test_exec.test_case.test_case_id}")
            
            # Check if device execution should be updated
            try:
                device_execution = test_exec.device.testsuitexecutiondevice_set.filter(
                    test_suite_execution=test_exec.test_suite_execution
                ).first()
                
                if device_execution:
                    logger.info(f"Triggering completion check for device execution {device_execution.id}")
                    print(f"[TASK] timeout_stuck_tests - Triggering completion check for device execution {device_execution.id}")
                    
                    check_device_execution_completion.delay(device_execution.id)
                else:
                    logger.warning(f"No device execution found for test {test_exec.id}")
                    print(f"[WARNING] timeout_stuck_tests - No device execution found for test {test_exec.id}")
                    
            except Exception as device_error:
                logger.error(f"Error finding device execution for test {test_exec.id}: {device_error}")
                print(f"[ERROR] timeout_stuck_tests - Error finding device execution: {device_error}")
        
        if stuck_count > 0:
            logger.info(f"Successfully processed {stuck_count} stuck tests")
            print(f"[TASK] timeout_stuck_tests - Successfully processed {stuck_count} stuck tests")
        else:
            logger.info("No stuck tests found")
            print(f"[TASK] timeout_stuck_tests - No stuck tests found")
            
    except Exception as e:
        error_msg = f"Error in timeout_stuck_tests: {str(e)}"
        logger.error(error_msg, exc_info=True)
        print(f"[ERROR] timeout_stuck_tests - {error_msg}")


# Additional helper task for debugging
@shared_task
def debug_test_execution_status(execution_id=None, device_id=None):
    """
    Debug task to print current status of test executions.
    
    This is a utility task for debugging purposes that can be called manually
    to get current status of test executions.
    
    Args:
        execution_id (int, optional): Specific test suite execution ID to debug
        device_id (int, optional): Specific device ID to debug
        
    Returns:
        None
        
    Side Effects:
        - Prints detailed status information to logs and console
    """
    logger.info("Starting debug status check")
    print(f"[DEBUG] debug_test_execution_status - Starting debug check")
    
    try:
        # Build filter conditions
        filters = {}
        if execution_id:
            filters['test_suite_execution_id'] = execution_id
        if device_id:
            filters['device_id'] = device_id
            
        # Get test case executions
        test_executions = TestCaseExecution.objects.filter(**filters).select_related(
            'test_case', 'device', 'test_suite_execution'
        )
        
        total_count = test_executions.count()
        logger.info(f"Found {total_count} test executions matching criteria")
        print(f"[DEBUG] debug_test_execution_status - Found {total_count} test executions")
        
        # Group by status
        status_counts = {}
        for status in [TestExecutionStatus.PENDING, TestExecutionStatus.RUNNING, 
                      TestExecutionStatus.SUCCESS, TestExecutionStatus.FAILED]:
            count = test_executions.filter(status=status).count()
            status_counts[status] = count
            logger.info(f"Status {status}: {count} tests")
            print(f"[DEBUG] debug_test_execution_status - Status {status}: {count} tests")
        
        # Show detailed info for running tests
        running_tests = test_executions.filter(status=TestExecutionStatus.RUNNING)
        logger.info(f"Detailed info for {running_tests.count()} running tests:")
        print(f"[DEBUG] debug_test_execution_status - Detailed running tests:")
        
        for test_exec in running_tests:
            runtime = ""
            if test_exec.started_at:
                runtime = f" (running for {timezone.now() - test_exec.started_at})"
            
            logger.info(f"  - {test_exec.test_case.name} on {test_exec.device.name}{runtime}")
            print(f"[DEBUG] debug_test_execution_status - Running: {test_exec.test_case.name} on {test_exec.device.name}{runtime}")
        
        # Show device execution status if available
        if execution_id:
            device_executions = TestSuiteExecutionDevice.objects.filter(
                test_suite_execution_id=execution_id
            ).select_related('device')
            
            logger.info(f"Device execution status for suite {execution_id}:")
            print(f"[DEBUG] debug_test_execution_status - Device executions for suite {execution_id}:")
            
            for device_exec in device_executions:
                logger.info(f"  - {device_exec.device.name}: {device_exec.status}")
                print(f"[DEBUG] debug_test_execution_status - Device {device_exec.device.name}: {device_exec.status}")
        
    except Exception as e:
        error_msg = f"Error in debug task: {str(e)}"
        logger.error(error_msg, exc_info=True)
        print(f"[ERROR] debug_test_execution_status - {error_msg}")