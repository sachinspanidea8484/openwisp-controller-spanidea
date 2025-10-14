# openwisp_test_management/tasks.py

import logging
import requests
from celery import shared_task, group, chain
from django.utils import timezone

# Load OpenWISP swapper models
from .swapper import load_model
from .base.models import TestExecutionStatus
from openwisp_controller.connection.models import DeviceConnection
from openwisp_controller.config.models import Config as DeviceConfig
from openwisp_controller.connection.connectors.ssh import Ssh

# Setup logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Load models
TestSuiteExecution = load_model("TestSuiteExecution")
TestSuiteExecutionDevice = load_model("TestSuiteExecutionDevice")
TestCaseExecution = load_model("TestCaseExecution")
TestSuiteCase = load_model("TestSuiteCase")

# Execution type: 1=SSH, 2=NB_API
DEVICE_EXECUTION_TYPE = 2

# Robot API server
ROBOT_SERVER_IP = "http://localhost:5000"  # move to settings in production

# ======================================================================================
# 1. MASTER TASK - RUN TEST SUITE ON MULTIPLE DEVICES (DEVICES PARALLEL, TESTS SEQUENTIAL)
# ======================================================================================
@shared_task
def execute_test_suite(execution_id):
    """
    Kick-off execution for a test suite across multiple devices.
    - Runs per-device executions in parallel (Celery group).
    """
    print(f"[TASK] execute_test_suite START execution_id={execution_id}")

    try:
        execution = TestSuiteExecution.objects.get(pk=execution_id)
        devices = TestSuiteExecutionDevice.objects.filter(
            test_suite_execution=execution
        ).select_related("device")

        print(f"[TASK] Found {devices.count()} devices for suite {execution_id}")

        # Launch devices in parallel
        device_tasks = [execute_tests_on_device.si(device_exec.id) for device_exec in devices]
        group(device_tasks).apply_async()

        print(f"[TASK] Launched parallel device executions for suite {execution_id}")

    except TestSuiteExecution.DoesNotExist:
        print(f"[ERROR] Suite execution {execution_id} not found")


# ======================================================================================
# 2. PER-DEVICE TASK - BUILD SEQUENTIAL TEST EXECUTION CHAIN
# ======================================================================================
@shared_task
def execute_tests_on_device(device_execution_id):
    """
    Orchestrates test case execution on a single device.
    - Builds a Celery `chain` of tasks (sequential).
    - Robot cases handled one-by-one.
    - Device agent tests handled one-by-one.
    """
    print(f"\n{'='*80}")
    print(f"[TASK] execute_tests_on_device START id={device_execution_id}")
    print(f"{'='*80}")

    try:
        device_exec = TestSuiteExecutionDevice.objects.get(pk=device_execution_id)
        device = device_exec.device
        suite_exec = device_exec.test_suite_execution
        ordered_cases = suite_exec.test_suite.get_ordered_test_cases()

        print(f"[TASK] Device={device.name} has {len(ordered_cases)} test cases")

        # Mark device execution running
        device_exec.status = "running"
        device_exec.started_at = timezone.now()
        device_exec.save()

        # Device environment info
        device_config = DeviceConfig.objects.filter(device=device).first()
        device_data = {
            "device_name": device.name,
            "management_ip": device.management_ip,
            "device_id": str(device.id),
            "configuration": device_config.context if device_config else {}
        }

        case_chain = None
        for order, suite_case in enumerate(ordered_cases, start=1):
            test_case = suite_case.test_case

            # Create execution record
            test_exec = TestCaseExecution.objects.create(
                test_suite_execution=suite_exec,
                device=device,
                test_case=test_case,
                execution_order=order,
                status=TestExecutionStatus.PENDING,
            )
            print(f"[TASK] Created TestCaseExecution {test_exec.id} for {test_case.name}")

            # Choose task
            if test_case.test_type == 1:  # Robot
                case_task = execute_robot_test.si(test_exec.id, device_data)
                print(f"[TASK] Queued Robot Test case={test_case.name}")
            else:  # Device Agent
                case_task = execute_device_agent_test.si(test_exec.id, device_exec.id)
                print(f"[TASK] Queued Device Agent Test case={test_case.name}")

            case_chain = case_task if case_chain is None else case_chain | case_task

        # Run sequential tasks
        if case_chain:
            print(f"[TASK] Launching sequential chain for {device.name}")
            case_chain.apply_async(link=check_device_execution_completion.si(device_exec.id))

    except TestSuiteExecutionDevice.DoesNotExist:
        print(f"[ERROR] Device exec {device_execution_id} not found")


# ======================================================================================
# 3. DEVICE AGENT TEST EXECUTION
# ======================================================================================
@shared_task
def execute_device_agent_test(test_exec_id, device_exec_id):
    """
    Execute a Device Agent test case via SSH or NB_API.
    """
    print(f"[TASK] execute_device_agent_test START test_exec_id={test_exec_id}")
    test_exec = TestCaseExecution.objects.get(pk=test_exec_id)
    device = test_exec.device

    test_exec.status = TestExecutionStatus.RUNNING
    test_exec.started_at = timezone.now()
    test_exec.save()

    try:
        if DEVICE_EXECUTION_TYPE == 1:  # SSH
            print(f"[TASK] Running SSH test {test_exec.test_case.test_case_id}")
            conn = DeviceConnection.objects.filter(device=device, enabled=True).first()
            if not conn:
                raise Exception("No SSH connection found")
            ssh_conn = Ssh(conn.credentials.params, [device.management_ip])
            ssh_conn.connect()
            command = f"python3 /usr/bin/tests/Test_Cases/{test_exec.test_case.test_case_id}/{test_exec.test_case.test_case_id}.py"
            output, exit_code = ssh_conn.exec_command(command, timeout=3600, exit_codes=[0, 1], raise_unexpected_exit=False)
            ssh_conn.disconnect()

            test_exec.stdout = output
            test_exec.exit_code = exit_code
            test_exec.status = TestExecutionStatus.SUCCESS if exit_code == 0 else TestExecutionStatus.FAILED

        else:  # NB_API
            api_url = f"http://{device.management_ip}/cgi-bin/nb_script_runner.py?test_id={test_exec.test_case.test_case_id}&execution_id={test_exec.id}"
            print(f"[TASK] Calling NB_API {api_url}")
            response = requests.get(api_url, timeout=300)

            test_exec.stdout = response.text
            test_exec.exit_code = response.status_code
            test_exec.status = TestExecutionStatus.SUCCESS if response.status_code == 200 else TestExecutionStatus.FAILED

    except Exception as e:
        test_exec.error_message = str(e)
        test_exec.status = TestExecutionStatus.FAILED
    finally:
        test_exec.completed_at = timezone.now()
        test_exec.save()
        print(f"[TASK] Finished {test_exec.test_case.name} with status {test_exec.status}")


# ======================================================================================
# 4. ROBOT FRAMEWORK TEST EXECUTION
# ======================================================================================
@shared_task
def execute_robot_test(test_exec_id, device_data):
    """
    Execute a Robot Framework test case by calling external Robot Framework API.
    Each test is sent individually.
    """
    print(f"[TASK] execute_robot_test START test_exec_id={test_exec_id}")
    test_exec = TestCaseExecution.objects.get(pk=test_exec_id)

    test_exec.status = TestExecutionStatus.RUNNING
    test_exec.started_at = timezone.now()
    test_exec.save()

    try:
        api_url = f"{ROBOT_SERVER_IP}/api/v1/run-robot/"
        payload = {
            "device": device_data,
            "test_case": {
                "test_case_id": test_exec.test_case.test_case_id,
                "test_case_name": test_exec.test_case.name,
                "params": test_exec.test_case.params,
                "execution_id": str(test_exec.id),
            },
        }
        print(f"[TASK] Sending Robot test {payload['test_case']['test_case_id']} to API={api_url}")
        response = requests.post(api_url, json=payload, timeout=300)

        print(f"[TASK] Robot API response status={response.status_code}")
        test_exec.stdout = response.text[:2000]
        test_exec.exit_code = response.status_code
        test_exec.status = TestExecutionStatus.SUCCESS if response.status_code == 200 else TestExecutionStatus.FAILED

    except Exception as e:
        test_exec.error_message = str(e)
        test_exec.status = TestExecutionStatus.FAILED
        print(f"[ERROR] Robot test failed: {str(e)}")
    finally:
        test_exec.completed_at = timezone.now()
        test_exec.save()
        print(f"[TASK] Finished Robot test {test_exec.test_case.name} with status {test_exec.status}")


# ======================================================================================
# 5. DEVICE EXECUTION COMPLETION CHECK
# ======================================================================================
@shared_task
def check_device_execution_completion(device_exec_id):
    """
    Mark device execution as 'completed' when all test cases finished.
    Check if full suite finished across all devices.
    """
    print(f"[TASK] check_device_execution_completion START id={device_exec_id}")
    device_exec = TestSuiteExecutionDevice.objects.get(pk=device_exec_id)

    test_executions = TestCaseExecution.objects.filter(
        device=device_exec.device,
        test_suite_execution=device_exec.test_suite_execution
    )

    # If all cases finished, close device exec
    if all(te.status in [TestExecutionStatus.SUCCESS, TestExecutionStatus.FAILED] for te in test_executions):
        device_exec.status = "completed"
        device_exec.completed_at = timezone.now()
        device_exec.save()
        print(f"[TASK] Device execution {device_exec.id} completed.")

        # Close suite if all devices done
        suite_exec = device_exec.test_suite_execution
        remaining = TestSuiteExecutionDevice.objects.filter(
            test_suite_execution=suite_exec, status__in=["running", "pending"]
        )
        if not remaining.exists():
            suite_exec.is_executed = True
            suite_exec.save()
            print(f"[TASK] Suite execution {suite_exec.id} completed.")


# 6. TIMEOUT / STUCK TEST HANDLER
# ======================================================================================
def ping_host(ip, timeout=2):
    """
    Simple ping utility.
    Return True if host responds, False otherwise.
    """
    try:
        print(f"[DEBUG] Pinging {ip}")
        result = subprocess.run(
            ["ping", "-c", "1", "-W", str(timeout), ip],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        return result.returncode == 0
    except Exception as e:
        print(f"[ERROR] Ping failed for {ip}: {e}")
        return False


@shared_task
def timeout_stuck_tests(max_pending_minutes=30, max_running_minutes=60):
    """
    Periodic Task (setup with Celery Beat) to handle stuck test executions.

    - Finds all TestCaseExecutions still PENDING or RUNNING past their timeout.
    - For Device Agent tests: ping + optional HTTP check.
    - Marks stuck executions as FAILED with error message.

    Args:
        max_pending_minutes (int): how long a test can stay 'pending' before failing.
        max_running_minutes (int): how long a test can stay 'running' before failing.
    """
    print(f"\n{'='*80}")
    print("[TASK] timeout_stuck_tests START")
    print(f"{'='*80}")

    now = timezone.now()
    pending_threshold = now - timedelta(minutes=max_pending_minutes)
    running_threshold = now - timedelta(minutes=max_running_minutes)

    # Load executions
    stuck_pending = TestCaseExecution.objects.filter(
        status=TestExecutionStatus.PENDING,
        created__lt=pending_threshold
    ).select_related("device", "test_case")

    stuck_running = TestCaseExecution.objects.filter(
        status=TestExecutionStatus.RUNNING,
        started_at__lt=running_threshold
    ).select_related("device", "test_case")

    print(f"[TASK] Found {stuck_pending.count()} stuck PENDING tests")
    print(f"[TASK] Found {stuck_running.count()} stuck RUNNING tests")

    # Handle stuck PENDING
    for te in stuck_pending:
        device = te.device
        if te.test_case.test_type == 2:  # Device Agent
            # Check device connectivity
            if not ping_host(device.management_ip):
                te.status = TestExecutionStatus.FAILED
                te.error_message = "Device unreachable (ping failed)"
            else:
                te.status = TestExecutionStatus.FAILED
                te.error_message = "Execution stuck in pending state"
        else:
            te.status = TestExecutionStatus.FAILED
            te.error_message = "Robot test stuck in pending state"
        te.completed_at = now
        te.save()
        print(f"[TASK] Marked PENDING test {te.id} as FAILED ({te.error_message})")

    # Handle stuck RUNNING
    for te in stuck_running:
        device = te.device
        if te.test_case.test_type == 2:  # Device Agent
            if not ping_host(device.management_ip):
                te.status = TestExecutionStatus.FAILED
                te.error_message = "Device stopped responding"
            else:
                te.status = TestExecutionStatus.FAILED
                te.error_message = "Execution exceeded max running time"
        else:
            te.status = TestExecutionStatus.FAILED
            te.error_message = "Robot test exceeded max running time"
        te.completed_at = now
        te.save()
        print(f"[TASK] Marked RUNNING test {te.id} as FAILED ({te.error_message})")

    print(f"[TASK] timeout_stuck_tests DONE at {timezone.now()}")
    print(f"{'='*80}\n")


# ======================================================================================
# 7. RETRY SINGLE TEST EXECUTION BY ID
# ======================================================================================
@shared_task
def retry_test_execution(test_exec_id):
    """
    Retry a failed or stuck test execution by ID.
    Can be triggered via Admin, API, or manually from shell.
    """
    print(f"\n{'='*80}")
    print(f"[TASK] retry_test_execution START execution_id={test_exec_id}")
    print(f"{'='*80}")

    try:
        test_exec = TestCaseExecution.objects.get(pk=test_exec_id)
        device = test_exec.device
        suite_exec = test_exec.test_suite_execution

        # Reset fields
        test_exec.status = TestExecutionStatus.PENDING
        test_exec.started_at = None
        test_exec.completed_at = None
        test_exec.stdout = ""
        test_exec.stderr = ""
        test_exec.error_message = ""
        test_exec.exit_code = None
        test_exec.execution_duration = None
        test_exec.retry_count = test_exec.retry_count + 1
        test_exec.save()

        print(f"[TASK] Test execution {test_exec_id} reset to PENDING (retry #{test_exec.retry_count})")

        # Device Agent Test
        if test_exec.test_case.test_type == 2:
            print(f"[TASK] Retrying Device Agent test: {test_exec.test_case.name}")
            # queue async
            execute_device_agent_test.delay(test_exec.id, suite_exec.test_device_executions.get(device=device).id)

        # Robot Framework Test
        elif test_exec.test_case.test_type == 1:
            print(f"[TASK] Retrying Robot test: {test_exec.test_case.name}")

            device_config = DeviceConfig.objects.filter(device=device).first()
            device_data = {
                "device_name": device.name,
                "management_ip": device.management_ip,
                "device_id": str(device.id),
                "configuration": device_config.context if device_config else {}
            }

            execute_robot_test.delay(test_exec.id, device_data)

        else:
            print(f"[ERROR] Unknown test type {test_exec.test_case.test_type} for execution {test_exec.id}")

    except TestCaseExecution.DoesNotExist:
        print(f"[ERROR] Test execution {test_exec_id} does not exist")
    except Exception as e:
        print(f"[ERROR] retry_test_execution failed: {str(e)}")


# CELERY_BEAT_SCHEDULE = {
#     "check-stuck-tests": {
#         "task": "openwisp_test_management.tasks.timeout_stuck_tests",
#         "schedule": crontab(minute="*/10"),  # every 10 minutes
#         "args": (30, 60),  # pending>30min, running>60min
#     },
# }
