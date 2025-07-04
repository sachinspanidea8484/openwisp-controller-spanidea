# openwisp_test_management/tasks.py
import logging
from celery import shared_task
from django.utils import timezone
from openwisp_controller.connection.connectors.ssh import Ssh
from openwisp_controller.connection.models import DeviceConnection
from .swapper import load_model
from .base.models import TestExecutionStatus

logger = logging.getLogger(__name__)

TestSuiteExecution = load_model("TestSuiteExecution")
TestSuiteExecutionDevice = load_model("TestSuiteExecutionDevice")
TestCaseExecution = load_model("TestCaseExecution")
TestSuiteCase = load_model("TestSuiteCase")


@shared_task
def execute_test_suite(execution_id):

    """
    Main task to execute a test suite on all devices
    """
    try:
        execution = TestSuiteExecution.objects.get(pk=execution_id)
        
        # Get all device executions
        device_executions = TestSuiteExecutionDevice.objects.filter(
            test_suite_execution=execution
        ).select_related('device')
        
        # Launch individual device executions
        for device_execution in device_executions:
            execute_tests_on_device.delay(device_execution.id)
            
    except Exception as e:
        logger.error(f"Error executing test suite {execution_id}: {str(e)}")

@shared_task
def execute_tests_on_device(device_execution_id):
    """
    Execute all test cases on a single device - launches parallel test executions
    """

    try:
        device_execution = TestSuiteExecutionDevice.objects.get(pk=device_execution_id)
        print(">>>>>>>>>>>>>>>>>>>>>>>>>>execute_test_suite<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<",device_execution_id)
        print(">>>>>>>>>>>>>>>>>>>>>>>>>>device_execution<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<",device_execution)
        # return
        device = device_execution.device
        test_suite_execution = device_execution.test_suite_execution
        
        # Update status to running
        device_execution.status = 'running'
        device_execution.started_at = timezone.now()
        device_execution.save()
        
        # Get device connection
        try:
            device_conn = DeviceConnection.objects.get(
                device=device,
                is_working=True,
                enabled=True
            )
        except DeviceConnection.DoesNotExist:
            device_execution.status = 'failed'
            device_execution.output = "No working connection found"
            device_execution.completed_at = timezone.now()
            device_execution.save()
            return
        
        # Get ordered test cases (but we'll execute them in parallel)
        print(">>>>>>>>>>>>>>>>>>>>>>>>>>test_suite_execution<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<",test_suite_execution)
        test_cases = test_suite_execution.test_suite.get_ordered_test_cases()
        print(">>>>>>>>>>>>>>>>>>>>>>>>>>test_cases<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<",test_cases)

        
        # Create TestCaseExecution records for all test cases
        test_execution_ids = []
        for suite_case in test_cases:
            test_case = suite_case.test_case
            
            # Only create execution records for Device Agent type tests (type=1)
            if test_case.test_type == 1:
                test_execution = TestCaseExecution.objects.create(
                    test_suite_execution=test_suite_execution,
                    device=device,
                    test_case=test_case,
                    # execution_order=suite_case.order,  # Commented out as requested
                    status=TestExecutionStatus.PENDING,
                )
                test_execution_ids.append(test_execution.id)
        
        # Now launch ALL test cases in parallel
        for test_execution_id in test_execution_ids:
            execute_single_test_case.delay(
                test_execution_id,
                device_conn.credentials.params,
                device.last_ip,
                device_execution_id
            )
        
        # Don't mark device as completed here - let another task check completion
        check_device_execution_completion.delay(device_execution_id)
        
    except Exception as e:
        logger.error(f"Error setting up tests on device: {str(e)}")
        device_execution.status = 'failed'
        device_execution.output = f"Setup error: {str(e)}"
        device_execution.completed_at = timezone.now()
        device_execution.save()

@shared_task
def execute_single_test_case(test_execution_id, ssh_params, device_ip, device_execution_id):
    """
    Execute a single test case - this runs in parallel with other test cases
    """
    try:
        test_execution = TestCaseExecution.objects.get(pk=test_execution_id)
        test_case = test_execution.test_case
        
        # Update status to running
        test_execution.status = TestExecutionStatus.RUNNING
        test_execution.started_at = timezone.now()
        test_execution.save()
        
        # Create SSH connection for this specific test
        ssh_conn = Ssh(ssh_params, [device_ip])
        
        try:
            ssh_conn.connect()
            
            # Execute the test
            # test_path = f"/usr/bin/tests/{test_case.test_case_id}/{test_case.test_case_id}.py"
            # command = f"python3 {test_path}"

            test_path = f"/usr/bin/tests/{test_case.test_case_id}"
            command = f"sh {test_path}"
            
            logger.info(f"Executing test {test_case.test_case_id} on {device_ip}")
            
            output, exit_code = ssh_conn.exec_command(
                command,
                timeout=300,  # 5 minutes max per test
                exit_codes=[0, 1, 2, 3, 4, 5],  # Accept multiple exit codes
                raise_unexpected_exit=False
            )

            
            # Save results
            test_execution.stdout = output
            test_execution.exit_code = exit_code
            test_execution.completed_at = timezone.now()
            
            if exit_code == 0:
                test_execution.status = TestExecutionStatus.SUCCESS
            else:
                test_execution.status = TestExecutionStatus.FAILED
                
            test_execution.save()
            
            logger.info(f"Test {test_case.test_case_id} completed with exit code {exit_code}")
            
        except Exception as e:
            logger.error(f"Error executing test {test_case.test_case_id}: {str(e)}")
            test_execution.status = TestExecutionStatus.FAILED
            test_execution.error_message = str(e)
            test_execution.completed_at = timezone.now()
            test_execution.save()
        finally:
            try:
                ssh_conn.disconnect()
            except:
                pass
        
        # Check if all tests are done for this device
        check_device_execution_completion.delay(device_execution_id)
        
    except Exception as e:
        logger.error(f"Error in single test execution: {str(e)}")

@shared_task
def check_device_execution_completion(device_execution_id, retry_count=0):
    """
    Check if all tests are completed for a device and update status
    """
    try:
        device_execution = TestSuiteExecutionDevice.objects.get(pk=device_execution_id)
        test_suite_execution = device_execution.test_suite_execution
        
        # Count pending/running tests
        pending_or_running = TestCaseExecution.objects.filter(
            test_suite_execution=test_suite_execution,
            device=device_execution.device,
            status__in=[TestExecutionStatus.PENDING, TestExecutionStatus.RUNNING],
            # test_type=1 # Device Agent
        ).count()
        
        if pending_or_running > 0:
            # Not all tests completed, check again in 5 seconds
            if retry_count < 600:  # Max 50 minutes of checking (600 * 5 seconds)
                check_device_execution_completion.apply_async(
                    args=[device_execution_id, retry_count + 1],
                    countdown=5  # Check again in 5 seconds
                )
                return
        
        # All tests completed, update device execution status
        logger.info(f"All tests completed for device {device_execution.device.name}")
        
        # Get all test executions for this device
        test_executions = TestCaseExecution.objects.filter(
            test_suite_execution=test_suite_execution,
            device=device_execution.device
        ).order_by('test_case__name')  # Order by name since we're not using execution_order
        
        # Build summary
        output_lines = []
        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        
        output_lines.append(f"Test Execution Summary for {device_execution.device.name}")
        output_lines.append("=" * 60)
        
        for test_exec in test_executions:
            total_tests += 1
            duration = ""
            
            if test_exec.execution_duration:
                duration = f" ({test_exec.formatted_duration})"
            elif test_exec.started_at and test_exec.completed_at:
                duration_delta = test_exec.completed_at - test_exec.started_at
                duration = f" ({int(duration_delta.total_seconds())}s)"
            
            if test_exec.status == TestExecutionStatus.SUCCESS:
                passed_tests += 1
                output_lines.append(f"✓ {test_exec.test_case.name}: PASSED{duration}")
                if test_exec.stdout.strip():
                    output_lines.append(f"   Output: {test_exec.stdout.strip()[:100]}...")
            else:
                failed_tests += 1
                output_lines.append(f"✗ {test_exec.test_case.name}: FAILED{duration}")
                if test_exec.error_message:
                    output_lines.append(f"   Error: {test_exec.error_message}")
                if test_exec.stdout.strip():
                    output_lines.append(f"   Output: {test_exec.stdout.strip()[:100]}...")
        
        output_lines.append("=" * 60)
        output_lines.append(f"Total: {total_tests} | Passed: {passed_tests} | Failed: {failed_tests}")
        
        # Update device execution
        device_execution.status = 'completed' if failed_tests == 0 else 'failed'
        device_execution.output = "\n".join(output_lines)
        device_execution.completed_at = timezone.now()
        device_execution.save()
        
        # Check if all devices are done
        check_suite_execution_completion.delay(test_suite_execution.id)
        
    except Exception as e:
        logger.error(f"Error checking device completion: {str(e)}")

@shared_task
def check_suite_execution_completion(suite_execution_id):
    """
    Check if all devices have completed execution
    """
    try:
        # Count devices still running
        pending_devices = TestSuiteExecutionDevice.objects.filter(
            test_suite_execution_id=suite_execution_id,
            status__in=['pending', 'running']
        ).count()
        
        if pending_devices == 0:
            logger.info(f"Test suite execution {suite_execution_id} completed on all devices")
            # Here you could send notifications, generate reports, etc.
            
    except Exception as e:
        logger.error(f"Error checking suite completion: {str(e)}")

# Optional: Task to monitor long-running tests
@shared_task
def timeout_stuck_tests():
    """
    Run periodically to timeout tests that are stuck
    This should be scheduled to run every few minutes
    """
    from datetime import timedelta
    
    timeout_threshold = timezone.now() - timedelta(minutes=30)  # 30 minute timeout
    
    # Find stuck tests
    stuck_tests = TestCaseExecution.objects.filter(
        status=TestExecutionStatus.RUNNING,
        started_at__lt=timeout_threshold
    )
    
    for test_exec in stuck_tests:
        logger.warning(f"Timing out stuck test: {test_exec.test_case.test_case_id} on {test_exec.device.name}")
        test_exec.timeout_execution("Test execution exceeded 30 minute timeout")
        
        # Check if device execution should be updated
        check_device_execution_completion.delay(
            test_exec.device.testsuitexecutiondevice_set.filter(
                test_suite_execution=test_exec.test_suite_execution
            ).first().id
        )

            