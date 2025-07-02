# openwisp_test_management/tasks.py
import logging
from celery import shared_task
from django.utils import timezone
import paramiko

from .swapper import load_model

logger = logging.getLogger(__name__)

TestSuiteExecution = load_model("TestSuiteExecution")
TestSuiteExecutionDevice = load_model("TestSuiteExecutionDevice")
TestCase = load_model("TestCase")


@shared_task
def run_command_on_device(device_ip, username, password, command):
    # device_model = load_model("TestSuiteExecutionDevice")
    # for device in device_model.objects.get(all):
    #     if device.id==device_id:
    #         executiondevice = device
    #         break

    print("Running test on device: ", device_ip, command)
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    ssh.connect(
        hostname=device_ip,
        username=username,
        password=password,
        look_for_keys=False
    )   

    stdin, stdout, stderr = ssh.exec_command(command)
    output = stdout.read().decode()
    error = stderr.read().decode()

    ssh.close()

    return output

@shared_task
def execute_test_suite_on_devices(execution_id):
    """
    Execute a test suite on all devices in the execution
    """
    try:
        execution = TestSuiteExecution.objects.get(pk=execution_id)
    except TestSuiteExecution.DoesNotExist:
        logger.error(f"TestSuiteExecution {execution_id} not found")
        return
    
    # Get all devices for this execution
    device_executions = TestSuiteExecutionDevice.objects.filter(
        test_suite_execution=execution,
        status='pending'
    )
    
    for device_execution in device_executions:
        # Trigger individual device execution
        execute_test_suite_on_device.delay(device_execution.pk)
    
    # Mark execution as started
    execution.is_executed = True
    execution.save()


@shared_task
def execute_test_suite_on_device(device_execution_id):
    """
    Execute a test suite on a single device
    """
    try:
        device_execution = TestSuiteExecutionDevice.objects.get(pk=device_execution_id)
    except TestSuiteExecutionDevice.DoesNotExist:
        logger.error(f"TestSuiteExecutionDevice {device_execution_id} not found")
        return
    
    # Update status to running
    device_execution.status = 'running'
    device_execution.started_at = timezone.now()
    device_execution.save()
    
    try:
        # Get device connection
        device = device_execution.device
        connection = device.deviceconnection
        
        if not connection.is_working:
            raise Exception("Device connection is not working")
        
        # Get test cases in the suite
        test_suite = device_execution.test_suite_execution.test_suite
        test_cases = test_suite.get_ordered_test_cases()
        
        output_lines = []
        all_passed = True
        
        # Execute each test case
        for suite_case in test_cases:
            test_case = suite_case.test_case
            
            # Here you would implement actual SSH command execution
            # For now, we'll simulate it
            output_lines.append(f"Executing test: {test_case.name} (ID: {test_case.test_case_id})")
            print(output_lines)
            # Simulate test execution via SSH
            # command = f"run_test {test_case.test_case_id}"
            # result = connection.connector.exec_command(command)
            
            # Simulated result
            result = {"success": True, "output": "Test passed"}
            
            if result["success"]:
                output_lines.append(f"✓ {test_case.name}: PASSED")
            else:
                output_lines.append(f"✗ {test_case.name}: FAILED")
                output_lines.append(f"  Error: {result['output']}")
                all_passed = False
        
        # Update device execution status
        device_execution.status = 'completed' if all_passed else 'failed'
        device_execution.output = "\n".join(output_lines)
        
    except Exception as e:
        logger.error(f"Error executing test suite on device {device_execution.device.name}: {str(e)}")
        device_execution.status = 'failed'
        device_execution.output = f"Execution error: {str(e)}"
    
    finally:
        device_execution.completed_at = timezone.now()
        device_execution.save()


@shared_task
def check_execution_completion(execution_id):
    """
    Check if all devices have completed execution
    """
    try:
        execution = TestSuiteExecution.objects.get(pk=execution_id)
    except TestSuiteExecution.DoesNotExist:
        return
    
    # Check if all devices are done
    pending_count = TestSuiteExecutionDevice.objects.filter(
        test_suite_execution=execution,
        status__in=['pending', 'running']
    ).count()
    
    if pending_count == 0:
        # All devices completed
        # Here you could send notifications, generate reports, etc.
        logger.info(f"Test suite execution {execution_id} completed on all devices")
