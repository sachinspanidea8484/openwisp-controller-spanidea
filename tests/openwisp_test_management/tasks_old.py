# openwisp_test_management/tasks.py
import logging
from celery import shared_task
from django.utils import timezone
from openwisp_controller.connection.connectors.ssh import Ssh
from openwisp_controller.connection.models import DeviceConnection
from .swapper import load_model

logger = logging.getLogger(__name__)

TestSuiteExecution = load_model("TestSuiteExecution")
TestSuiteExecutionDevice = load_model("TestSuiteExecutionDevice")
TestCaseExecution = load_model("TestCaseExecution")

@shared_task
def execute_test_suite(execution_id):
    # print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>📋📋📋📋📋📋📋📋📋📋📋📋📋📋📋📋📋📋📋📋📋")
    # logger.info(f"Error executing test suite {execution_id}")
    # return
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
    Execute all test cases on a single device
    """
    try:
        device_execution = TestSuiteExecutionDevice.objects.get(pk=device_execution_id)
        device = device_execution.device
        test_suite_execution = device_execution.test_suite_execution
        
        # Update status to running
        device_execution.status = 'running'
        device_execution.started_at = timezone.now()
        device_execution.save()
        
        # Get device connection using OpenWISP's DeviceConnection
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
        
        # Get SSH parameters
        params = device_conn.credentials.params
        addresses = [device.last_ip] if device.last_ip else []
        
        # Create SSH connection using OpenWISP's connector
        ssh_conn = Ssh(params, addresses)
        
        try:
            ssh_conn.connect()
            # Get ordered test cases
            test_cases = test_suite_execution.test_suite.get_ordered_test_cases()

            count = len(test_cases)

            # print("Total Test Cases:", count)
            # for case in test_cases:
            #  print(vars(case))
            # return
            output_lines = []
            all_passed = True
            
            for suite_case in test_cases:

                test_case = suite_case.test_case
                
                # Only execute Agent type tests (type=1)
                if test_case.test_type == 1:
                    # Create test case execution record
                    test_execution = TestCaseExecution.objects.create(
                        test_suite_execution=test_suite_execution,
                        device=device,
                        test_case=test_case,
                        execution_order=suite_case.order,
                        status='running',
                        started_at=timezone.now()
                    )
                    
                    # Execute test case
                    # test_path = f"/usr/bin/tests/{test_case.test_case_id}/{test_case.test_case_id}.py"
                    # command = f"python3 {test_path}"

                    test_path = f"/usr/bin/tests/{test_case.test_case_id}"
                    command = f"sh {test_path}"
                    
                    try:
                        output, exit_code = ssh_conn.exec_command(
                            command,
                            # timeout=60,  # 60 seconds timeout per test
                            exit_codes=[0, 1],  # Accept 0 and 1 as valid exit codes
                            raise_unexpected_exit=False
                        )
                        
                        print("555555555555555555555🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>" ,output)
                        print("555555555555555555555📋📋📋📋📋📋📋📋📋📋📋📋📋📋📋📋📋📋📋📋📋>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>" ,exit_code)





                        # Update test case execution
                        test_execution.stdout = output
                        test_execution.exit_code = exit_code
                        test_execution.completed_at = timezone.now()
                        
                        if exit_code == 0:
                            # test_execution.status = 'success'
                            output_lines.append(f"✓ {test_case.name}: PASSED")
                        else:
                            test_execution.status = 'failed'
                            all_passed = False
                            output_lines.append(f"✗ {test_case.name}: FAILED (exit code: {exit_code})")
                            
                    except Exception as e:
                        test_execution.status = 'failed'
                        test_execution.error_message = str(e)
                        test_execution.completed_at = timezone.now()
                        all_passed = False
                        output_lines.append(f"✗ {test_case.name}: ERROR - {str(e)}")
                    
                    test_execution.save()
                    
                else:
                    # Skip Robot Framework tests for now
                    output_lines.append(f"⚠️  {test_case.name}: SKIPPED (Robot Framework)")
            
            # Update device execution status
            device_execution.status = 'completed' if all_passed else 'failed'
            device_execution.output = "\n".join(output_lines)
            
        except Exception as e:
            logger.error(f"SSH connection error: {str(e)}")
            device_execution.status = 'failed'
            device_execution.output = f"Connection error: {str(e)}"
        finally:
            ssh_conn.disconnect()
            device_execution.completed_at = timezone.now()
            device_execution.save()
            
    except Exception as e:
        logger.error(f"Error executing tests on device: {str(e)}")