# openwisp_test_management/tasks.py
import logging
from celery import shared_task
from django.utils import timezone
from openwisp_controller.connection.connectors.ssh import Ssh
from openwisp_controller.connection.models import DeviceConnection
from openwisp_controller.config.models import Config as DeviceConfig
from openwisp_monitoring.monitoring.models import Metric

from uuid import UUID
from .swapper import load_model
from .base.models import TestExecutionStatus
import requests
import os
import subprocess
import json
from django.core.mail import EmailMultiAlternatives
import csv
from datetime import datetime
from django.template.loader import render_to_string, get_template, TemplateDoesNotExist
import io
from datetime import timedelta

from .settings import EXECUTOR_SERVER_IP ,OPENWISP_SERVER_IP ,MEDIA_URL ,EMAIL_HOST_USER
from .base.models import TestExecutionStatus

from django.urls import reverse

from django.db import transaction
from django.core.cache import cache
import time
# Create logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Capture all levels

# LOG_FILE_PATH = "/var/log/openwisp/openwisp_test_management.log"
LOG_FILE_PATH = "/opt/openwisp/logs/openwisp_test_management.log"

# Configure logger for this module
# os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)



# File handler
# file_handler = logging.FileHandler(LOG_FILE_PATH, mode='a')
# file_handler.setLevel(logging.DEBUG)
# file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
# logger.addHandler(file_handler)

# Load models using swapper pattern for better modularity
TestSuiteExecution = load_model("TestSuiteExecution")
TestSuiteExecutionDevice = load_model("TestSuiteExecutionDevice")
TestCaseExecution = load_model("TestCaseExecution")
TestSuiteCase = load_model("TestSuiteCase")
ScheduledExecution= load_model("ScheduledExecution")
TestCase= load_model("TestCase")
ExecutionArtifact= load_model("ExecutionArtifact")
ExecutionEmailLog = load_model("ExecutionEmailLog")

# Device Execution Type Configuration
DEVICE_EXECUTION_TYPE = 1 # 1 for SSH, 0 for MQTT (default is SSH)

# ============================================================================
# CONSTANTS & CONFIGURATION
# ============================================================================

EMAIL_BATCH_SIZE = 10  # Process emails in batches
EMAIL_RATE_LIMIT = "10/m"  # Rate limit: 10 emails per minute
EMAIL_MAX_RETRIES = 3
EMAIL_RETRY_DELAY = 60  # seconds
LOCK_TIMEOUT = 300  # 5 minutes lock timeout

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
        
        #update execution start time
        execution.execution_start_time= timezone.now()
        execution.save(update_fields= ["execution_start_time"])

        # Launch individual device executions in parallel
        for device_execution in device_executions:
            logger.info(f"Launching tests on device: {device_execution.device.name} (ID: {device_execution.id})")
            print(f"[TASK] execute_test_suite - Launching device execution ID: {device_execution.id} for device: {device_execution.device.name}")
            
            # Queue the device execution task
            if not device_execution.device.is_deleted:
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

def is_device_reachable(device_id):
    # Get ping metric status
    device_status = "Offline"
    try:
        ping_metric = Metric.objects.get(
            object_id=device_id,
            configuration='ping',
            key='ping',
        )

        device_status = "Online" if ping_metric.is_healthy else "Offline"

    except Metric.DoesNotExist:
        logger.debug(f"ping_metric {ping_metric} ")
        device_status = "Offline"
    if device_status == "Online":
        return True
    else:
        return False

@shared_task
def execute_tests_on_device(device_execution_id):
    """
    Execute all test cases on a single device by sending them to executor server.
    """
    logger.info(f"Starting device execution with ID: {device_execution_id}")
    print(f"[TASK] execute_tests_on_device - Starting device execution ID: {device_execution_id}")

    try:
        # Retrieve the device execution record
        device_execution = TestSuiteExecutionDevice.objects.get(pk=device_execution_id)
        device_execution_connection_protocol = getattr(device_execution, 'connection_protocol', 0) or 0
        logger.info(f"Retrieved device execution: {device_execution}")
        print(f"[TASK] execute_tests_on_device - Retrieved device execution: {device_execution}")
        
        device = device_execution.device
        test_suite_execution = device_execution.test_suite_execution
        
        logger.info(f"Device: {device.name} (ID: {device.id})")
        
        
        # Update device execution status to running
        device_execution.status = 'running'
        device_execution.started_at = timezone.now()
        device_execution.save()
        
        logger.info(f"Updated device execution status to 'running' at {device_execution.started_at}")
        print(f"[TASK] execute_tests_on_device - Updated status to 'running' at {device_execution.started_at}")
        
        # Check device connection based on protocol
        # device_conn = None
        # has_connection = False
        # connection_error = None
        
        # For SSH (protocol = 1), connection is required
        # if device_execution_connection_protocol == 1:
        #     try:
        #         device_conn = DeviceConnection.get_working_connection(device)
        #         has_connection = True
        #         logger.info(f"Found working SSH connection: {device_conn}")
        #         print(f"[TASK] execute_tests_on_device - Found working SSH connection: {device_conn}")
                    
        #     except DeviceConnection.DoesNotExist:
        #         connection_error = f"SSH connection required but not found for device {device.name}"
        #         logger.error(connection_error)
        #         print(f"[ERROR] execute_tests_on_device - {connection_error}")
                
        #     except Exception as e:
        #         connection_error = f"Device {device.name} is unreachable via SSH: {str(e)}"
        #         logger.error(connection_error)
        #         print(f"[ERROR] execute_tests_on_device - {connection_error}")
        
        # # For MQTT (protocol = 0), connection is optional
        # else:
        #     try:
        #         device_conn = DeviceConnection.get_working_connection(device)
        #         has_connection = True
        #         logger.info(f"Found working MQTT connection: {device_conn}")
        #         print(f"[TASK] execute_tests_on_device - Found working MQTT connection: {device_conn}")
        #     except:
        #         # For MQTT, no connection is acceptable
        #         logger.info(f"No connection found for MQTT device {device.name}, proceeding without it")
        #         print(f"[TASK] execute_tests_on_device - MQTT device, no connection required")
         

        cred_info = DeviceConnection.get_credentials(device)
        device_conn = cred_info['connection']
        has_connection = cred_info['has_connection']
        # Get ordered test cases from the test suite
        if test_suite_execution.test_selection_type == 1:
            test_cases = test_suite_execution.test_suite.get_ordered_test_cases()
            
        elif test_suite_execution.test_selection_type ==0 :
            
            ordered_ids= [UUID(tc_id) for tc_id in test_suite_execution.test_case_execution_order]
           
            testcase_map = TestCase.objects.in_bulk(ordered_ids)
           
            test_cases= [
                testcase_map[tc_id] for tc_id in ordered_ids if tc_id in testcase_map
            ]
           
            # test_cases= test_suite_execution.individual_test_cases.all()
        total_test_cases = len(test_cases)
        
        logger.info(f"Retrieved {total_test_cases} test cases from test suite")
        print(f"[TASK] execute_tests_on_device - Retrieved {total_test_cases} test cases")
        
        all_test_execution_ids = []
        device_config = DeviceConfig.objects.filter(device=device).first()

        device_data = {
            "device_name": device.name,
            "management_ip": device.management_ip,
            "device_id": device.id,
            "ssh": {
                "host": device.management_ip,
                "username": cred_info['credentials']['username'],
                "password": cred_info['credentials']['password']
            },
            "configuration": device_config.context if device_config else {}
        }

        print("device_data>>>>>>>>", device_data)
        
        test_suite_data = {
            "test_suite_execution_id": test_suite_execution.id,
            "test_cases": []
        }
        if test_suite_execution.test_selection_type==1:
            test_suite_data["test_suite_name"] = test_suite_execution.test_suite.name
            test_suite_data["test_suite_id"]= test_suite_execution.test_suite.id
        
        # Create execution records for ALL test cases
        for suite_case in test_cases:
            if test_suite_execution.test_selection_type==1:
                test_case = suite_case.test_case
            else:
                test_case=suite_case
            
            logger.info(f"Creating execution record for test: {test_case.name} (Type: {test_case.get_test_type_display()})")
            print(f"[TASK] execute_tests_on_device - Creating execution record for: {test_case.name}")
            
            # Check if we can proceed with execution
            # Always create pending execution - executor handles connection testing
            test_execution = TestCaseExecution.objects.create(
                        test_suite_execution=test_suite_execution,
                        device=device,
                        test_case=test_case,
                        status=TestExecutionStatus.PENDING,
)
            test_execution.save()
            all_test_execution_ids.append(test_execution.id)
            
            if test_execution and test_execution.id:
                print(f"✅ Successfully created TestCaseExecution with ID: {test_execution.id}")
           
            artifact= ExecutionArtifact.objects.filter(
             device= device,
             testcase=test_case,
             execution= test_suite_execution
            ).only("config_file", "is_pushed").first()

            # ✅ NEW: Prepare file parameters
            is_file_required = test_case.is_configuration_push_required
            file_download_url = None


            if artifact and artifact.config_file and not artifact.is_pushed:
             # Build full download URL
             from django.conf import settings
             file_path = artifact.config_file.name  # e.g., "execution_artifacts/test.zip"
             file_download_url = f"{MEDIA_URL}{file_path}"
             # If MEDIA_URL is relative, make it absolute
             if not file_download_url.startswith('http'):
                          # Get base URL from request or settings
                          base_url = OPENWISP_SERVER_IP
                          file_download_url = f"{base_url}{file_download_url}"


            logger.debug(f"is_file_required >>>>>>>>: {is_file_required}")
            logger.debug(f"file_download_url>>>>>>>>: {file_download_url}")

           
            # Add to test suite data for executor server
            test_suite_data["test_cases"].append({
                "test_case_id": test_case.test_case_id,
                "test_case_name": test_case.name,
                "test_type": test_case.test_type,
                "params": test_case.params,
                "execution_id": test_execution.id,
                "is_file_required": is_file_required,  # ✅ NEW
                "file_download_url": file_download_url  # ✅ NEW
            })
            
            logger.debug(f"Created TestCaseExecution ID: {test_execution.id}")
            print(f"[DEBUG] execute_tests_on_device - Created TestCaseExecution ID: {test_execution.id}")
        
        logger.info(f"Created {len(all_test_execution_ids)} test execution records out of {total_test_cases} total tests")
        print(f"[TASK] execute_tests_on_device - Created {len(all_test_execution_ids)} tests out of {total_test_cases} total")
        
        # Always send to executor server - it handles connection testing
        if all_test_execution_ids:
                logger.info(f"Sending {len(all_test_execution_ids)} test cases to executor server")
                print(f"[TASK] Sending {len(all_test_execution_ids)} tests to executor server")

                execute_tests_on_executor_server.delay(
                                all_test_execution_ids,
                                device_data,
                                test_suite_data,
                                device_execution_id,
                                device_execution_connection_protocol
                )
        else:
                logger.warning("No tests found to execute")
                print(f"[WARNING] execute_tests_on_device - No tests found")
        
        # Start completion checking
        logger.info("Starting completion checking process")
        print(f"[TASK] execute_tests_on_device - Starting completion checking")
        # check_device_execution_completion.delay(device_execution_id)
        # check_execution_completion.delay(device_execution_id)
        
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
def execute_selected_tests_in_test_execution(execution_id, device_tests_info_list):
    """
    Main task to execute selected tests in execution.
    
    This is the entry point for selected tests execution. It:
    1. Retrieves the test suite execution record
    2. Gets all associated device executions
    3. Launches parallel execution tasks for each device
    
    Args:
        execution_id (int): Primary key of the TestSuiteExecution record
        exedevice_tests_info_listcution_id (list): device tests list
        
    Returns:
        None
        
    Raises:
        Exception: Logs any errors that occur during execution setup
    """
    logger.info(f"Starting selected tests for execution with ID: {execution_id}")
    # print(f"🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️🖥️: {execution_id})")
    try:
        # Retrieve the test suite execution record
        execution = TestSuiteExecution.objects.get(pk=execution_id)
        logger.info(f"Retrieved test suite execution: {execution}")
        print(f"[TASK] execute_selected_tests_in_test_execution - Retrieved execution: {execution}")
        
        # Get all device executions associated with this test suite execution
        device_executions = TestSuiteExecutionDevice.objects.filter(
            test_suite_execution=execution
        ).select_related('device')
        
        device_count = device_executions.count()
        logger.info(f"Found {device_count} devices to execute tests on")
        print(f"[TASK] execute_selected_tests_in_test_execution - Found {device_count} devices")
        # Launch individual device executions in parallel
        for device_execution in device_executions:
            logger.info(f"Launching tests on device: {device_execution.device.name} (ID: {device_execution.id})")
            print(f"[TASK] execute_selected_tests_in_test_execution - Launching device execution ID: {device_execution.id} for device: {device_execution.device.name}")
            print(f"Launching tests for testcount: {len(device_tests_info_list.get(str(device_execution.device.id), [])) }")
            print(f"List: {device_tests_info_list}")
            if len(device_tests_info_list.get(str(device_execution.device.id), [])) > 0:
                # Queue the device execution task
                execute_selected_tests_on_device.delay(device_execution.id, device_tests_info_list[str(device_execution.device.id)])

        logger.info(f"Successfully queued test execution for {device_count} devices")
        print(f"[TASK] execute_selected_tests_in_test_execution - Successfully queued {device_count} device executions")
        
    except TestSuiteExecution.DoesNotExist:
        error_msg = f"Test suite execution with ID {execution_id} not found"
        logger.error(error_msg)
        print(f"[ERROR] execute_selected_tests_in_test_execution - {error_msg}")
        
    except Exception as e:
        error_msg = f"Error executing test suite {execution_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        print(f"[ERROR] execute_selected_tests_in_test_execution - {error_msg}")

@shared_task
def execute_selected_tests_on_device(device_execution_id, selected_test_ids):
    """
    Execute selected test cases on a single device by sending them to executor server.
    """
    logger.info(f"Starting device execution with ID: {device_execution_id}")
    print(f"[TASK] execute_selected_tests_on_device - Starting device execution ID: {device_execution_id}")

    try:
        # Retrieve the device execution record
        device_execution = TestSuiteExecutionDevice.objects.get(pk=device_execution_id)
        device_execution_connection_protocol = getattr(device_execution, 'connection_protocol', 0) or 0
        logger.info(f"Retrieved device execution: {device_execution}")
        print(f"[TASK] execute_selected_tests_on_device - Retrieved device execution: {device_execution}")
        
        device = device_execution.device
        test_suite_execution = device_execution.test_suite_execution
        
        logger.info(f"Device: {device.name} (ID: {device.id})")
        
        
        # Update device execution status to running
        device_execution.status = 'running'
        device_execution.started_at = timezone.now()
        device_execution.save()
        
        logger.info(f"Updated device execution status to 'running' at {device_execution.started_at}")
        print(f"[TASK] execute_selected_tests_on_device - Updated status to 'running' at {device_execution.started_at}")
        
        # Get credentials without testing connection (executor will handle SSH testing)
        cred_info = DeviceConnection.get_credentials(device)
        device_conn = cred_info['connection']
        has_connection = cred_info['has_connection']

        logger.info(f"Retrieved credentials for device: {device.name} (has_connection: {has_connection})")
        print(f"[TASK] execute_selected_tests_on_device - Credentials retrieved: {has_connection}")
         
        
        # Get ordered test cases from the test suite
        if test_suite_execution.test_selection_type == 1:
            test_cases = test_suite_execution.test_suite.get_ordered_test_cases()
            
        elif test_suite_execution.test_selection_type ==0 :
            
            ordered_ids= [UUID(tc_id) for tc_id in test_suite_execution.test_case_execution_order]
           
            testcase_map = TestCase.objects.in_bulk(ordered_ids)
           
            test_cases= [
                testcase_map[tc_id] for tc_id in ordered_ids if tc_id in testcase_map
            ]

        total_test_cases = len(selected_test_ids)
        
        logger.info(f"Retrieved {total_test_cases} test cases for execution")
        print(f"[TASK] execute_selected_tests_on_device - Retrieved {total_test_cases} test cases")
        
        all_test_execution_ids = []
        device_config = DeviceConfig.objects.filter(device=device).first()

        device_data = {
            "device_name": device.name,
            "management_ip": device.management_ip,
            "device_id": device.id,
            "ssh": {
                "host": device.management_ip,
                "username": cred_info['credentials']['username'],
                "password": cred_info['credentials']['password']
            },
            "configuration": device_config.context if device_config else {}
        }

        print("device_data>>>>>>>>", device_data)
        
        test_suite_data = {
            "test_suite_execution_id": test_suite_execution.id,
            "test_cases": []
        }
        if test_suite_execution.test_selection_type==1:
            test_suite_data["test_suite_name"] = test_suite_execution.test_suite.name
            test_suite_data["test_suite_id"]= test_suite_execution.test_suite.id

        selected_ids = set(selected_test_ids)

        if test_suite_execution.test_selection_type == 1:
            selected_test_cases = [
                tc.test_case for tc in test_cases
                if tc.test_case.test_case_id in selected_ids
            ]
        else:
            selected_test_cases = [
                tc for tc in test_cases
                if tc.test_case_id in selected_ids
            ]

        # Create execution records for ALL selected test cases
        for test_case in selected_test_cases:
            logger.info(f"Creating execution record for test: {test_case.name} (Type: {test_case.get_test_type_display()})")
            print(f"[TASK] execute_selected_tests_on_device - Creating execution record for: {test_case.name}")
            
            # Always create pending execution - executor handles connection testing
            test_execution = TestCaseExecution.objects.create(
                        test_suite_execution=test_suite_execution,
                        device=device,
                        test_case=test_case,
                        status=TestExecutionStatus.PENDING,
)
            test_execution.save()
            all_test_execution_ids.append(test_execution.id)
            
            if test_execution and test_execution.id:
                print(f"✅ Successfully created TestCaseExecution with ID: {test_execution.id}")
            
            artifact= ExecutionArtifact.objects.filter(
             device= device,
             testcase=test_case,
             execution= test_suite_execution
            ).only("config_file", "is_pushed").first()

            # ✅ NEW: Prepare file parameters
            is_file_required = test_case.is_configuration_push_required
            file_download_url = None


            if artifact and artifact.config_file and not artifact.is_pushed:
             # Build full download URL
             from django.conf import settings
             file_path = artifact.config_file.name  # e.g., "execution_artifacts/test.zip"
             file_download_url = f"{MEDIA_URL}{file_path}"
             # If MEDIA_URL is relative, make it absolute
             if not file_download_url.startswith('http'):
                          # Get base URL from request or settings
                          base_url = OPENWISP_SERVER_IP
                          file_download_url = f"{base_url}{file_download_url}"


            logger.debug(f"is_file_required >>>>>>>>: {is_file_required}")
            logger.debug(f"file_download_url>>>>>>>>: {file_download_url}")

            # Add to test suite data for executor server
            test_suite_data["test_cases"].append({
                "test_case_id": test_case.test_case_id,
                "test_case_name": test_case.name,
                "test_type": test_case.test_type,
                "params": test_case.params,
                "execution_id": test_execution.id,
                "is_file_required": is_file_required,  # ✅ NEW
                "file_download_url": file_download_url  # ✅ NEW
            })
            
            logger.debug(f"Created TestCaseExecution ID: {test_execution.id}")
            print(f"[DEBUG] execute_selected_tests_on_device - Created TestCaseExecution ID: {test_execution.id}")
        
        logger.info(f"Created {len(all_test_execution_ids)} test execution records out of {total_test_cases} total tests")
        print(f"[TASK] execute_selected_tests_on_device - Created {len(all_test_execution_ids)} tests out of {total_test_cases} total")
        
        # Always send to executor server - it handles connection testing
        if all_test_execution_ids:
                logger.info(f"Sending {len(all_test_execution_ids)} test cases to executor server")
                print(f"[TASK] Sending {len(all_test_execution_ids)} tests to executor server")

                # Send all tests to executor server
                execute_tests_on_executor_server.delay(
                                all_test_execution_ids,
                                device_data,
                                test_suite_data,
                                device_execution_id,
                                device_execution_connection_protocol
                )
        else:
                logger.warning("No tests found to execute")
                print(f"[WARNING] execute_selected_tests_on_device - No tests found")
        
        # Start completion checking
        logger.info("Starting completion checking process")
        print(f"[TASK] execute_selected_tests_on_device - Starting completion checking")
        check_device_execution_completion.delay(device_execution_id)
        
    except TestSuiteExecutionDevice.DoesNotExist:
        error_msg = f"Device execution with ID {device_execution_id} not found"
        logger.error(error_msg)
        print(f"[ERROR] execute_selected_tests_on_device - {error_msg}")
        
    except Exception as e:
        error_msg = f"Error setting up tests on device: {str(e)}"
        logger.error(error_msg, exc_info=True)
        print(f"[ERROR] execute_selected_tests_on_device - {error_msg}")
        
        try:
            device_execution.status = 'failed'
            device_execution.output = f"Setup error: {str(e)}"
            device_execution.completed_at = timezone.now()
            device_execution.save()
            logger.info("Updated device execution status to 'failed'")
            print(f"[TASK] execute_selected_tests_on_device - Updated status to 'failed'")
        except:
            logger.error("Failed to update device execution status")
            print(f"[ERROR] execute_selected_tests_on_device - Failed to update status")


@shared_task
def execute_tests_on_executor_server(test_execution_ids, device_data, test_suite_data, device_execution_id ,device_execution_connection_protocol):
    """
    Execute ALL test cases (Device Agent + Robot Framework) on executor server.
    The executor server will handle how to trigger each test case.
    """
    print(f"\n{'='*80}")
    print(f"[DEBUG] UNIFIED TEST EXECUTION ON EXECUTOR SERVER")
    print(f"{'='*80}")
    
    logger.info(f"Executing {len(test_execution_ids)} test cases on executor server")
    
    # Convert UUIDs to strings
    test_execution_ids_str = [str(id) for id in test_execution_ids]
    
    # Fix device_data UUIDs
    device_data_fixed = {
        "device_name": device_data.get('device_name', 'N/A'),
        "management_ip": device_data.get('management_ip', 'N/A'),
        "device_id": str(device_data.get('device_id', '')),
        "reachable": is_device_reachable(str(device_data.get('device_id', ''))),
        "ssh": device_data.get('ssh', {}),
        "configuration": device_data.get('configuration', {}),
        "connection_protocol" : device_execution_connection_protocol
    }
    
    # Fix test_suite_data UUIDs
    test_suite_data_fixed = {
        "test_suite_name": test_suite_data.get('test_suite_name', 'N/A'),
        "test_suite_id": str(test_suite_data.get('test_suite_id', '')),
        "test_suite_execution_id": str(test_suite_data.get('test_suite_execution_id', '')),
        "test_cases": []
    }
    
    # Fix test case execution IDs and include test type
    for test_case in test_suite_data.get('test_cases', []):
        print(">>>>>>>>>>>>>>>>>>>>test_case", test_case)
        test_suite_data_fixed["test_cases"].append({
            "test_case_id": test_case.get('test_case_id', 'N/A'),
            "test_case_name": test_case.get('test_case_name', 'N/A'),
            "test_type": test_case.get('test_type', 1),  # Include test type
            "execution_id": str(test_case.get('execution_id', '')),
            "params": test_case.get('params', {}),
            "is_file_required": test_case.get('is_file_required', False),
            "file_download_url": test_case.get('file_download_url', ""),

        })


    
    # Extract device_execution_id
    device_execution_id_str = str(device_execution_id)
    
    # Debug: Print input parameters
    print(f"\n[DEBUG] Input Parameters (after UUID conversion):")
    print(f"[DEBUG] Number of test executions: {len(test_execution_ids_str)}")
    print(f"[DEBUG] Test execution IDs: {test_execution_ids_str}")
    
    print(f"\n[DEBUG] Device Data:")
    print(f"  - Device Name: {device_data_fixed.get('device_name', 'N/A')}")
    print(f"  - Device ID: {device_data_fixed.get('device_id', 'N/A')}")
    print(f"  - Device IP: {device_data_fixed.get('management_ip', 'N/A')}")
    
    print(f"\n[DEBUG] Test Suite Data:")
    print(f"  - Suite Name: {test_suite_data_fixed.get('test_suite_name', 'N/A')}")
    print(f"  - Suite ID: {test_suite_data_fixed.get('test_suite_id', 'N/A')}")
    print(f"  - Device Execution ID: {device_execution_id_str}")
    print(f"  - Number of test cases: {len(test_suite_data_fixed.get('test_cases', []))}")
    
    print(f"\n[DEBUG] Test Cases to Execute:")
    for idx, test_case in enumerate(test_suite_data_fixed.get('test_cases', []), 1):
        test_type_display = "Robot Framework" if test_case.get('test_type') == 1 else "Device"
        print(f"  {idx}. Test Case ID: {test_case.get('test_case_id', 'N/A')}")
        print(f"     Test Case Name: {test_case.get('test_case_name', 'N/A')}")
        print(f"     Test Type: {test_type_display}")
        print(f"     Execution ID: {test_case.get('execution_id', 'N/A')}")
    

    sorted_test_cases = sorted(
    test_suite_data_fixed.get('test_cases', []),
    key=lambda x: x.get('test_case_name', '')
    )
    print(f"     Sort Test Cases: {sorted_test_cases}")
    sorted_test_cases
    # Prepare API payload
    api_payload = {
        "devices": [device_data_fixed],
        "test_suites": {
            "test_suite_name": test_suite_data_fixed.get('test_suite_name'),
            "test_suite_id": test_suite_data_fixed.get('test_suite_id'),
            "test_suite_execution_id": test_suite_data_fixed.get('test_suite_execution_id'),
            "test_cases": test_suite_data_fixed.get('test_cases', [])  # Changed from sorted_test_cases

        },
        "execution_metadata": {
            "device_execution_id": device_execution_id_str,
            "test_execution_ids": test_execution_ids_str
        }
    }
    
    print(f"\n[DEBUG] API Payload prepared")
    executor_api_url = f"{EXECUTOR_SERVER_IP}/api/v1/run-test/"
    
    print(f"\n🔍 [DEBUG] Making API Call:")
    print(f"📍 [DEBUG] API URL: {executor_api_url}")
    print(f"📮 [DEBUG] Method: POST")
    print(f"⏱️  [DEBUG] Timeout: 300 seconds")
    
    # Check if API is reachable first
    try:
        print(f"🔄 [DEBUG] Checking if executor server is reachable....")
        base_url = executor_api_url.rsplit('/', 2)[0]
        test_response = requests.get(base_url, timeout=60)
        print(f"✅ [DEBUG] Executor server is reachable at {base_url}")
    except Exception as e:
        print(f"❌ [ERROR] Cannot reach executor server: {e}")
        print(f"⚠️  [ERROR] Make sure the server at {executor_api_url} is running")
        
        # Mark all tests as failed
        for exec_id in test_execution_ids:
            try:
                test_exec = TestCaseExecution.objects.get(pk=exec_id)
                test_exec.status = TestExecutionStatus.FAILED
                test_exec.error_message = f"Executor server unreachable: {str(e)}"
                test_exec.stderr = "Connection failed - Executor server unreachable"
                test_exec.completed_at = timezone.now()
                test_exec.save()
            except Exception as update_error:
                logger.error(f"Error updating test {exec_id}: {update_error}")
        return
    
    try:
        print(f"[DEBUG] Sending request to executor server...")
        
        response = requests.post(
            executor_api_url,
            json=api_payload,
            timeout=300  # Quick timeout just to submit the job
        )
        
        print(f"\n[DEBUG] API Response:")
        print(f"[DEBUG] Status Code: {response.status_code}")
        print(f"[DEBUG] Response Headers: {dict(response.headers)}")
        
        try:
            response_json = response.json()
            print(f"[DEBUG] Response Body: {response_json}")
        except:
            print(f"[DEBUG] Response Body (text): {response.text[:500]}...")
        
        if response.status_code == 200:
            logger.info("Executor server API called successfully")
            print(f"\n[DEBUG] ✅ API call successful! Tests submitted to executor server")
            
            # Update test execution records to running (optional - executor can do this)
            for idx, exec_id in enumerate(test_execution_ids, 1):
                try:
                    test_exec = TestCaseExecution.objects.get(pk=exec_id)
                    # You can keep them as PENDING since executor will update them
                    # Or mark as RUNNING here
                    print(f"[DEBUG] Test execution {exec_id} submitted to executor")
                    
                except TestCaseExecution.DoesNotExist:
                    print(f"[DEBUG] ❌ Test execution {exec_id} not found in database!")
                    logger.error(f"Test execution {exec_id} not found")
                    
                except Exception as e:
                    print(f"[DEBUG] ❌ Error with test execution {exec_id}: {str(e)}")
                    logger.error(f"Error with test execution {exec_id}: {str(e)}")
                    
        else:
            logger.error(f"Executor server API call failed: {response.status_code}")
            print(f"\n[DEBUG] ❌ API call failed! Status: {response.status_code}")
            print(f"[DEBUG] Marking all tests as failed...")
            
            # Mark tests as failed
            for idx, exec_id in enumerate(test_execution_ids, 1):
                try:
                    test_exec = TestCaseExecution.objects.get(pk=exec_id)
                    test_exec.status = TestExecutionStatus.FAILED
                    test_exec.error_message = f"Executor server API call failed: {response.status_code}"
                    test_exec.stdout = response.text[:1000] if response.text else "No response"
                    test_exec.completed_at = timezone.now()
                    test_exec.save()
                    
                    print(f"[DEBUG] ✅ Marked test execution {exec_id} as FAILED")
                    
                except Exception as e:
                    print(f"[DEBUG] ❌ Error updating failed test {exec_id}: {str(e)}")
                    logger.error(f"Error updating failed test {exec_id}: {str(e)}")
                    
    except requests.exceptions.Timeout:
        print(f"\n[DEBUG] ❌ API call timed out!")
        logger.error("Executor server API call timed out")
        
        # Mark all tests as failed due to timeout
        for exec_id in test_execution_ids:
            try:
                test_exec = TestCaseExecution.objects.get(pk=exec_id)
                test_exec.status = TestExecutionStatus.FAILED
                test_exec.error_message = "Executor server API timeout"
                test_exec.completed_at = timezone.now()
                test_exec.save()
                print(f"[DEBUG] Marked test {exec_id} as FAILED due to timeout")
            except Exception as e:
                print(f"[DEBUG] Error updating test {exec_id} after timeout: {str(e)}")
                
    except Exception as e:
        print(f"\n[DEBUG] ❌ Unexpected error calling executor server API!")
        print(f"[DEBUG] Error type: {type(e).__name__}")
        print(f"[DEBUG] Error message: {str(e)}")
        
        logger.error(f"Error calling executor server API: {str(e)}")
        
        # Mark all tests as failed due to error
        for exec_id in test_execution_ids:
            try:
                test_exec = TestCaseExecution.objects.get(pk=exec_id)
                test_exec.status = TestExecutionStatus.FAILED
                test_exec.error_message = f"API error: {str(e)}"
                test_exec.completed_at = timezone.now()
                test_exec.save()
                print(f"[DEBUG] Marked test {exec_id} as FAILED due to error")
            except Exception as update_error:
                print(f"[DEBUG] Error updating test {exec_id} after API error: {str(update_error)}")
    
    print(f"\n[DEBUG] Executor server test execution task completed")
    print(f"{'='*80}\n")
@shared_task
def retry_test_execution(test_execution_id):
    """
    Retry a single test execution by sending to executor server
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
            device_execution_connection_protocol = getattr(device_execution, 'connection_protocol', 0) or 0

        except TestSuiteExecutionDevice.DoesNotExist:
            logger.error(f"Device execution not found for test execution {test_execution_id}")
            return
        
        # Get credentials without testing connection (executor will handle SSH testing)
        cred_info = DeviceConnection.get_credentials(device)
        device_conn = cred_info['connection']
        has_connection = cred_info['has_connection']

        logger.info(f"Retrieved credentials for retry: {device.name} (has_connection: {has_connection})")
        print(f"[TASK] retry_test_execution - Credentials retrieved: {has_connection}")
        
        # Reset the test execution status
        test_execution.status = TestExecutionStatus.PENDING
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
        
        # Prepare test case data
        test_case = test_execution.test_case
        test_suite_name = ""
        test_suite_id = ""
        if test_suite_execution.test_selection_type == 1:
            test_suite_name = test_suite_execution.test_suite.name
            test_suite_id = test_suite_execution.test_suite.id

        device_config = DeviceConfig.objects.filter(device=device).first()
        
        # Prepare data for executor server
        device_data = {
            "device_name": device.name,
            "management_ip": device.management_ip,
            "device_id": device.id,
            "ssh": {
                "host": device.management_ip,
                "username": cred_info['credentials']['username'],
                "password": cred_info['credentials']['password']
            },
            "configuration": device_config.context if device_config else {}
        }
        artifact= ExecutionArtifact.objects.filter(
         device= device,
         testcase=test_case,
         execution= test_suite_execution
        ).only("config_file", "is_pushed").first()

        # ✅ NEW: Prepare file parameters
        is_file_required = test_case.is_configuration_push_required
        file_download_url = None

        if artifact and artifact.config_file and not artifact.is_pushed:
         from django.conf import settings
         file_path = artifact.config_file.name
         file_download_url = f"{MEDIA_URL}{file_path}"
         if not file_download_url.startswith('http'):
                  base_url = OPENWISP_SERVER_IP
                  file_download_url = f"{base_url}{file_download_url}"
        

        
        test_suite_data = {
            "test_suite_name": test_suite_name,
            "test_suite_id": test_suite_id,
            "test_suite_execution_id": test_suite_execution.id,
            "test_cases": [{
                "test_case_id": test_case.test_case_id,
                "test_case_name": test_case.name,
                "test_type": test_case.test_type,
                "params": test_case.params,
                "execution_id": test_execution_id,
                "is_file_required": is_file_required,  # ✅ NEW
                "file_download_url": file_download_url  # ✅ NEW
            }]
        }
        
        # Send to executor server
        logger.info(f"Sending retry to executor server for test: {test_case.name}")
        execute_tests_on_executor_server.delay(
            [test_execution_id],
            device_data,
            test_suite_data,
            device_execution_id,
            device_execution_connection_protocol
        )
        
        logger.info(f"Successfully queued retry for test execution {test_execution_id}")
        
    except TestCaseExecution.DoesNotExist:
        logger.error(f"Test execution {test_execution_id} not found")
    except Exception as e:
        logger.error(f"Error retrying test execution {test_execution_id}: {str(e)}")
        print(f"[ERROR] retry_test_execution - Error: {str(e)}")



@shared_task
def abort_device_pending_tests(test_group_execution_id, device_id):
    """
    Abort all pending tests for test execution
    """
    try:
        abort_pending_tests_api_url = f"{EXECUTOR_SERVER_IP}/api/v1/abort-pending-tests/"
        abort_pending_tests_api_payload = {
            "test_group_execution_id": str(test_group_execution_id),
            "device_id": device_id
        }
        # Check if API is reachable first
        try:
            print(f"🔄 [DEBUG] Checking if executor server is reachable....")
            base_url = abort_pending_tests_api_url.rsplit('/', 2)[0]
            test_response = requests.get(base_url, timeout=60)
            print(f"✅ [DEBUG] Executor server is reachable at {base_url}")
        except Exception as e:
            print(f"❌ [ERROR] Cannot reach executor server: {e}")
            print(f"⚠️  [ERROR] Make sure the server at {abort_pending_tests_api_url} is running")
            return

        print(f"[DEBUG] Sending abort pending tests request to executor server...")
        response = requests.post(
                abort_pending_tests_api_url,
                json=abort_pending_tests_api_payload,
                timeout=300  # Quick timeout just to submit the job
            )
        print(f"\n[DEBUG] API Response:")
        print(f"[DEBUG] Status Code: {response.status_code}")
        print(f"[DEBUG] Response Headers: {dict(response.headers)}")
        
        try:
            response_json = response.json()
            print(f"[DEBUG] Response Body: {response_json}")
        except:
            print(f"[DEBUG] Response Body (text): {response.text[:500]}...")
        
        if response.status_code == 200:
            logger.info("Executor server API called successfully")
            print(f"\n[DEBUG] ✅ API call successful! Tests submitted to executor server")
        else:
            logger.error(f"Executor server API call failed: {response.status_code}")
            print(f"\n[DEBUG] ❌ API call failed! Status: {response.status_code}")
    except Exception as e:
        logger.error(f"Error aborting pending tests for device execution {device_id }: {str(e)}")
        print(f"[ERROR] abort_device_pending_tests - Error: {str(e)}")


@shared_task
def abort_test_execution(test_execution_id):
    """
    Abort a running test execution
    """
    from .swapper import load_model
    TestCaseExecution = load_model("TestCaseExecution")
    TestSuiteExecutionDevice = load_model("TestSuiteExecutionDevice")
    
    try:
        test_execution = TestCaseExecution.objects.get(pk=test_execution_id)
        test_case = test_execution.test_case
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
        
        # Get credentials without testing connection (executor will handle SSH testing)
        cred_info = DeviceConnection.get_credentials(device)
        device_conn = cred_info['connection']
        has_connection = cred_info['has_connection']

        logger.info(f"Retrieved credentials for abort: {device.name} (has_connection: {has_connection})")
        print(f"[TASK] abort_test_execution - Credentials retrieved: {has_connection}")

        device_data = {
            "device_name": test_execution.device.name,
            "management_ip": test_execution.device.management_ip,
            "device_id": str(test_execution.device.id),
            "ssh": {
                "host": test_execution.device.management_ip,
                "username": cred_info['credentials']['username'],
                "password": cred_info['credentials']['password']
            }
        }
        
        logger.info(f"Aborting test execution {test_execution_id})")
        print(f"[TASK] abort_test_execution - Aborting test {test_execution_id}")

        api_payload = {
            "device": device_data,
            "test_id": str(test_execution.test_case.test_case_id),
            "execution_id": str(test_execution_id),
            "test_type": test_execution.test_case.test_type,
            "process_id": getattr(test_execution, 'process_id', 0) or 0,
            "connection_protocol" :  getattr(device_execution, 'connection_protocol', 0) or 0 # 0: MQTT 1: SSH SACHIN CHANGES
        }
        print(f"\n[DEBUG] API Payload prepared")
        abort_api_url = f"{EXECUTOR_SERVER_IP}/api/v1/abort-test/"
    
        print(f"\n🔍 [DEBUG] Making API Call:")
        print(f"📍 [DEBUG] API URL: {abort_api_url}")
        print(f"📮 [DEBUG] Method: POST")
        print(f"⏱️  [DEBUG] Timeout: 300 seconds")
    
        # Check if API is reachable first
        try:
            print(f"🔄 [DEBUG] Checking if executor server is reachable....")
            base_url = abort_api_url.rsplit('/', 2)[0]
            test_response = requests.get(base_url, timeout=60)
            print(f"✅ [DEBUG] Executor server is reachable at {base_url}")
        except Exception as e:
            print(f"❌ [ERROR] Cannot reach executor server: {e}")
            print(f"⚠️  [ERROR] Make sure the server at {abort_api_url} is running")
        
        # Mark all tests as failed
            try:
                test_execution.status = TestExecutionStatus.FAILED
                test_execution.error_message = f"Executor server unreachable: {str(e)}"
                test_execution.stderr = "Connection failed - Executor server unreachable"
                test_execution.completed_at = timezone.now()
                test_execution.save()
            except Exception as update_error:
                logger.error(f"Error updating test {test_execution_id}: {update_error}")
            return
    
        try:
            print(f"[DEBUG] Sending abort request to executor server...")
            
            response = requests.post(
                abort_api_url,
                json=api_payload,
                timeout=300  # Quick timeout just to submit the job
            )
                
        
            print(f"\n[DEBUG] API Response:")
            print(f"[DEBUG] Status Code: {response.status_code}")
            print(f"[DEBUG] Response Headers: {dict(response.headers)}")
        
            try:
                response_json = response.json()
                print(f"[DEBUG] Response Body: {response_json}")
            except:
                print(f"[DEBUG] Response Body (text): {response.text[:500]}...")
        
            if response.status_code == 200:
                logger.info("Executor server API called successfully")
                print(f"\n[DEBUG] ✅ API call successful! Tests submitted to executor server")
                
                    
            else:
                logger.error(f"Executor server API call failed: {response.status_code}")
                print(f"\n[DEBUG] ❌ API call failed! Status: {response.status_code}")
                print(f"[DEBUG] Marking all tests as failed...")
                
                # Mark tests as failed
                try:
                    test_execution.status = TestExecutionStatus.FAILED
                    test_execution.error_message = f"Executor server API call failed: {response.status_code}"
                    test_execution.stdout = response.text[:1000] if response.text else "No response"
                    test_execution.completed_at = timezone.now()
                    test_execution.save()
                    
                    print(f"[DEBUG] ✅ Marked test execution {test_execution_id} as FAILED")
                    
                except Exception as e:
                    print(f"[DEBUG] ❌ Error updating failed test {test_execution_id}: {str(e)}")
                    logger.error(f"Error updating failed test {test_execution_id}: {str(e)}")
                    
        except requests.exceptions.Timeout:
            print(f"\n[DEBUG] ❌ API call timed out!")
            logger.error("Executor server API call timed out")
        
            # Mark all tests as failed due to timeout
            try:
                test_execution.status = TestExecutionStatus.FAILED
                test_execution.error_message = "Executor server API timeout"
                test_execution.completed_at = timezone.now()
                test_execution.save()
                print(f"[DEBUG] Marked test {test_execution_id} as FAILED due to timeout")
            except Exception as e:
                print(f"[DEBUG] Error updating test {test_execution_id} after timeout: {str(e)}")
                
        except Exception as e:
            print(f"\n[DEBUG] ❌ Unexpected error calling executor server API!")
            print(f"[DEBUG] Error type: {type(e).__name__}")
            print(f"[DEBUG] Error message: {str(e)}")
            
            logger.error(f"Error calling executor server API: {str(e)}")
            
            # Mark all tests as failed due to error
            try:
                test_execution.status = TestExecutionStatus.FAILED
                test_execution.error_message = f"API error: {str(e)}"
                test_execution.completed_at = timezone.now()
                test_execution.save()
                print(f"[DEBUG] Marked test {test_execution_id} as FAILED due to error")
            except Exception as update_error:
                print(f"[DEBUG] Error updating test {test_execution_id} after API error: {str(update_error)}")
                
        logger.info(f"Successfully queued abort for test execution {test_execution_id}")
        
    except TestCaseExecution.DoesNotExist:
        logger.error(f"Test execution {test_execution_id} not found")
    except Exception as e:
        logger.error(f"Error aborting test execution {test_execution_id}: {str(e)}")
        print(f"[ERROR] abort_test_execution - Error: {str(e)}")

def ping_host(ip: str) -> bool:
    """
    Ping check using fping (Linux/Docker).
    Returns True if host is reachable, False otherwise.
    """
    try:
        command = ["fping", "-c1", "-t200", ip]
        print(f"[DEBUG] Running command: {' '.join(command)}")  # show command

        result = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        print(f"[DEBUG] Return code: {result.returncode}")
        print(f"[DEBUG] STDOUT: {result.stdout.strip()}")
        print(f"[DEBUG] STDERR: {result.stderr.strip()}")

        return result.returncode == 0
    except Exception as e:
        print(f"[ERROR] Ping check failed for {ip}: {str(e)}")
        return False

@shared_task
def timeout_stuck_tests():
    """
    New requirement:
    - Find all pending Device Agent test executions
    - For each device:
      → Check if pingable
      → Check if HTTP server reachable
      → If not reachable, mark execution as FAILED
    """
    logger.info("Starting check for pending Device Agent tests")
    print(f"[TASK] timeout_stuck_tests - Checking for pending Device Agent tests")


    # reachable = ping_host("127.0.0.1")

    TestCaseExecution = load_model("TestCaseExecution")

    try:
        # Find all pending test case executions where test type is Device Agent
        pending_agent_tests = TestCaseExecution.objects.filter(
            status=TestExecutionStatus.PENDING,
            test_case__test_type=2  # AGENT
        ).select_related("device")

        total = pending_agent_tests.count()
        logger.info(f"Found {total} pending Device Agent test executions")
        print(f"[TASK] timeout_stuck_tests - Found {total} pending Device Agent test executions")

        for test_exec in pending_agent_tests:
            device = test_exec.device
            management_ip = getattr(device, "management_ip", None)

            if not management_ip:
                logger.warning(f"Device {device.name} has no management_ip set")
                print(f"[WARNING] timeout_stuck_tests - Device {device.name} has no management_ip")
                continue

            logger.info(f"Checking device: {device.name} ({management_ip})")
            print(f"[TASK] Checking device: {device.name}, Management IP: {management_ip}")




            # Step 1: Check ICMP (ping)
            reachable = ping_host(management_ip)
            if not reachable:
                logger.warning(f"Ping failed for device {device.name} ({management_ip})")
                print(f"[ERROR] Device {device.name} not pingable at {management_ip}")

                # Mark execution as failed
                test_exec.status = TestExecutionStatus.FAILED
                test_exec.stdout = "Connection failed - device unreachable"
                test_exec.exit_code = -1
                test_exec.completed_at = timezone.now()
                test_exec.save(update_fields=["status", "stdout", "exit_code", "completed_at"])
                continue

            # Step 2: Check HTTP accessibility
            api_url = f"http://{management_ip}/"
            try:
                print(f"🔄 [DEBUG] Checking if HTTP server is reachable at {api_url}...")
                response = requests.get(api_url, timeout=10)

                if response.status_code == 200:
                    logger.info(f"HTTP server reachable at {api_url}")
                    print(f"[TASK] ✅ HTTP server reachable for device: {device.name}")
                else:
                    logger.warning(f"HTTP check failed with status {response.status_code} for {device.name}")
                    print(f"[WARNING] HTTP check failed for {device.name} ({management_ip}), status {response.status_code}")

                    # Mark execution as failed
                    test_exec.status = TestExecutionStatus.FAILED
                    test_exec.stdout = f"Connection failed - device unreachable"
                    test_exec.exit_code = response.status_code
                    test_exec.completed_at = timezone.now()
                    test_exec.save(update_fields=["status", "stdout", "exit_code", "completed_at"])

            except Exception as e:
                logger.error(f"HTTP server not reachable at {api_url} for {device.name}: {str(e)}")
                print(f"[ERROR] Device {device.name} ({management_ip}) HTTP server unreachable: {str(e)}")

                test_exec.status = TestExecutionStatus.FAILED
                test_exec.stdout = f"Connection failed - device unreachable"
                test_exec.exit_code = -1
                test_exec.completed_at = timezone.now()
                test_exec.save(update_fields=["status", "stdout", "exit_code", "completed_at"])

    except Exception as e:
        error_msg = f"Error in timeout_stuck_tests (pending Device Agent check): {str(e)}"
        logger.error(error_msg, exc_info=True)
        print(f"[ERROR] timeout_stuck_tests - {error_msg}")


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    time_limit=300,  # 5 minutes
    soft_time_limit=240  # 4 minutes
)
def check_and_execute_scheduled(self):
    """
    Check for due scheduled executions and trigger them.
    Runs every minute via Celery Beat.
    """
    
    
    # Prevent duplicate executions using cache lock
    lock_id = 'check_scheduled_executions_lock'
    acquire_lock = cache.add(lock_id, 'true', 50)  # Lock for 50 seconds
    
    if not acquire_lock:
        logger.info("Another instance is already running, skipping...")
        return "Skipped: Another instance running"
    
    try:
        from .models import ScheduledExecution
        
        
        execution_ids=[]
        with transaction.atomic():
            # Get pending executions that are due limit to 100 not to overwhelm
            due_executions = ScheduledExecution.objects.select_for_update(
                skip_locked=True
                ).filter(
                    status=ScheduledExecution.Status.PENDING,
                    scheduled_time__lte=timezone.now()
                )[:100]
            
            for scheduled in due_executions:
                scheduled.status= ScheduledExecution.Status.QUEUED
                scheduled.queued_at= timezone.now()
                scheduled.save(update_fields=['status','queued_at'])
                execution_ids.append(scheduled.id)


        count = len(execution_ids)
        logger.info(f"Found {count} due executions")
        
        
        # Trigger tasks outside transaction
        triggered = 0
        for scheduled_id in execution_ids:
            try:
                result = execute_scheduled_test.apply_async(
                    args=[scheduled_id],
                    countdown=0,
                    retry=True,
                    retry_policy={
                        'max_retries': 3,
                        'interval_start': 0,
                        'interval_step': 60,
                        'interval_max': 300,
                    }
                )
                
                # Store task ID for tracking
                ScheduledExecution.objects.filter(id=scheduled_id).update(
                    celery_task_id=result.id
                )
                
                logger.info(f"Task queued with ID: {result.id} for scheduled: {scheduled_id}")
                triggered += 1
                
            except Exception as e:
                logger.error(f"Failed to queue task for {scheduled_id}: {e}")
                # Revert status on failure
                ScheduledExecution.objects.filter(id=scheduled_id).update(
                    status=ScheduledExecution.Status.PENDING
                )
        
        return f"Triggered {triggered}/{count} executions"
        
    except Exception as exc:
        logger.error(f"Error in check_and_execute_scheduled: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=30)
    
    finally:
        cache.delete(lock_id)

@shared_task(
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True
)
def execute_scheduled_test(self, scheduled_execution_id):
    """
    Execute a specific scheduled test suite.
    """
    from .models import ScheduledExecution
    
    logger.info(f"Starting execution for scheduled ID: {scheduled_execution_id}")
    
    scheduled = None
    
    try:
        # Atomic status update with validation
        with transaction.atomic():
            scheduled = ScheduledExecution.objects.select_for_update().get(
                id=scheduled_execution_id
            )
            
            # Validate current status
            if scheduled.status == ScheduledExecution.Status.COMPLETED:
                logger.warning(f"Already completed: {scheduled_execution_id}")
                return f"Already completed: {scheduled_execution_id}"
            
            if scheduled.status == ScheduledExecution.Status.CANCELLED:
                logger.warning(f"Cancelled: {scheduled_execution_id}")
                return f"Cancelled: {scheduled_execution_id}"
            
            if scheduled.status == ScheduledExecution.Status.IN_PROCESS:
                logger.warning(f"Already running: {scheduled_execution_id}")
                # Check if it's stuck (running > 30 minutes)
                if scheduled.started_at and (timezone.now() - scheduled.started_at).seconds > 3600:
                    logger.error(f"Stuck execution detected: {scheduled_execution_id}")
                    scheduled.status = ScheduledExecution.Status.FAILED
                    scheduled.error_message = "Execution timeout - force killed"
                    scheduled.completed_at = timezone.now()
                    scheduled.save()
                    return f"Killed stuck execution: {scheduled_execution_id}"
                return f"Already running: {scheduled_execution_id}"
            
            # Check if execution is already executed
            if scheduled.execution.is_executed:
                logger.warning(f"Execution already completed: {scheduled.execution.id}")
                scheduled.status = ScheduledExecution.Status.COMPLETED
                scheduled.completed_at = timezone.now()
                scheduled.save()
                return f"Already executed: {scheduled.execution.id}"
            
            # Mark as IN_PROCESS
            scheduled.status = ScheduledExecution.Status.IN_PROCESS
            scheduled.started_at = timezone.now()
            scheduled.retry_count = self.request.retries  # Track retry attempts
            scheduled.save(update_fields=['status', 'started_at', 'retry_count'])
        
        # Execute outside transaction
        try:
            from .admin import TestSuiteExecutionAdmin
            
            admin = TestSuiteExecutionAdmin(
                model=scheduled.execution.__class__,
                admin_site=None
            )
            
            logger.info(f"Calling _start_execution for {scheduled.execution.id}")
            
            #  Add timeout monitoring
            start_time = time.time()
            
            # Execute with progress tracking
            admin._start_execution(None, scheduled.execution, False)
            
            execution_time = time.time() - start_time
            
            logger.info(
                f"Execution {scheduled_execution_id} completed "
                f"in {execution_time:.2f} seconds"
            )
            
            # Mark as completed
            with transaction.atomic():
                scheduled = ScheduledExecution.objects.select_for_update().get(
                    id=scheduled_execution_id
                )
                scheduled.status = ScheduledExecution.Status.COMPLETED
                scheduled.completed_at = timezone.now()
                scheduled.save(update_fields=['status', 'completed_at'])
            
            logger.info(f"Marked as COMPLETED: {scheduled_execution_id}")
            return f"Successfully executed {scheduled.execution}"
            
        except Exception as exec_error:
            logger.error(
                f"Execution error for {scheduled_execution_id}: {exec_error}",
                exc_info=True
            )
            
            # Mark as failed and prepare for retry
            with transaction.atomic():
                scheduled = ScheduledExecution.objects.select_for_update().get(
                    id=scheduled_execution_id
                )
                scheduled.status = ScheduledExecution.Status.FAILED
                scheduled.error_message = str(exec_error)[:1000]
                scheduled.retry_count = self.request.retries
                
                # Only set completed_at if max retries reached
                if self.request.retries >= self.max_retries:
                    scheduled.completed_at = timezone.now()
                
                scheduled.save()
            
            raise  # Re-raise to trigger Celery retry
            
    except ScheduledExecution.DoesNotExist:
        logger.error(f"Scheduled execution {scheduled_execution_id} not found")
        return f"Not found: {scheduled_execution_id}"
        
    except Exception as exc:
        logger.error(
            f"Fatal error in execute_scheduled_test {scheduled_execution_id}: {exc}",
            exc_info=True
        )
        
        # Mark as failed with proper error handling
        try:
            with transaction.atomic():
                scheduled = ScheduledExecution.objects.select_for_update().get(
                    id=scheduled_execution_id
                )
                scheduled.status = ScheduledExecution.Status.FAILED
                scheduled.error_message = str(exc)[:1000]
                scheduled.retry_count = self.request.retries
                scheduled.completed_at = timezone.now()
                scheduled.save()
        except Exception as save_error:
            logger.error(f"Could not save error status: {save_error}")
        
        raise


@shared_task
def cleanup_old_executions():
    """
    Clean up old completed/failed scheduled executions.
    Runs daily at 2 AM.
    """
    from .models import ScheduledExecution
    from datetime import timedelta
    
    cutoff_date = timezone.now() - timedelta(days=30)
    
    deleted_count, _ = ScheduledExecution.objects.filter(
        status__in=[
            ScheduledExecution.Status.COMPLETED,
            ScheduledExecution.Status.FAILED,
            ScheduledExecution.Status.CANCELLED
        ],
        updated_at__lt=cutoff_date
    ).delete()
    
    logger.info(f"Cleaned up {deleted_count} old scheduled executions")
    print(f"Cleaned up {deleted_count} old scheduled executions")
    
    return f"Cleaned up {deleted_count} records"



































## OLD 

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
        # test_execution.status = TestExecutionStatus.RUNNING
        # test_execution.started_at = timezone.now()
        # test_execution.save()
        
        logger.info(f"Updated test execution status to 'running' at {test_execution.started_at}")
        print(f"[TASK] execute_test_via_nb_api - Updated status to 'running'",device_ip)
        
        # Construct API URL
        api_url = f"http://{device_ip}/cgi-bin/nb_script_runner.py?test_id={test_case.test_case_id}&execution_id={test_execution_id}"


        try:
             print(f"🔄 [DEBUG] Checking if API is reachable...")
             base_url = api_url.rsplit('/', 2)[0]  # Get base URL
             test_response = requests.get(base_url, timeout=60)
             print(f"✅✅✅✅✅✅✅✅✅✅✅✅         ✅✅✅✅✅✅✅✅✅✅✅✅ [DEBUG] API server is reachable at {base_url}")
        except Exception as e:
             print(f"❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌ [ERROR] Cannot reach API server: {e}")
             print(f"⚠️  [ERROR] Make sure the server at {api_url} is running")
         # curl "http://10.10.10.20/cgi-bin/nb_script_runner.py?test_id=TestCase_001&execution_id=1001"

        logger.info(f"NB_API URL: {api_url}")
        print(f"[TASK] execute_test_via_nb_api - Calling API: {api_url}")
        
        try:
            # Make GET request with no timeout (wait indefinitely)
            # This ensures requests are processed sequentially on resource-limited devices
            logger.info(f"Starting NB_API request for test {test_case.test_case_id}")
            print(f"[TASK] execute_test_via_nb_api - Sending GET request (no timeout)")
            
            response = requests.get(
                api_url,
                timeout=300,  # No timeout - wait indefinitely
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
            test_execution.stdout = "Connection failed - device unreachable"
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
    return
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
                    countdown=30  # Check again in 1 hour (3600 seconds)

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
          # test_case__test_type=2  # Remove this line
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
                    
        #         if test_exec.stdout and test_exec.stdout.strip():
        #             output_lines.append(f"   Output: {test_exec.stdout.strip()[:100]}...")
        
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
    return
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






from django.contrib.auth import get_user_model
from openwisp_notifications.signals import notify
User = get_user_model()

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=5, retry_kwargs={"max_retries": 3})
def send_execution_completed_notification(self, instance_pk, created_by_id):
    return
    if not created_by_id:
        return

    with transaction.atomic():
        #  Lock row
        instance = (
            TestSuiteExecution.objects
            .select_for_update()
            .get(pk=instance_pk)
        )

        # Only completed executions
        if instance.execution_status != 3:
            return

        #  If already notified, exit
        if instance.completion_notification_sent:
            return

        #  Mark as notified BEFORE sending
        instance.completion_notification_sent = True
        instance.save(update_fields=["completion_notification_sent"])

    # Send notification AFTER lock is released
    recipient = User.objects.get(pk=created_by_id)

    notify.send(
        sender=instance,
        recipient=recipient,
        type="test_suite_execution_completed",
        target=instance,
        execution_name = instance.name,
    )

 













# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def format_duration(start, end):
    """Format duration between two timestamps"""
    if not start or not end:
        return "N/A"
    duration = end - start
    total_seconds = int(duration.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)


def get_execution_lock_key(execution_id):
    """Generate cache key for execution email lock"""
    return f"execution_email_lock_{execution_id}"


def get_email_lock_key(execution_id, email):
    """Generate cache key for individual email lock"""
    return f"email_lock_{execution_id}_{email}"


def acquire_lock(lock_key, timeout=LOCK_TIMEOUT):
    """Acquire a distributed lock using cache"""
    return cache.add(lock_key, "locked", timeout)


def release_lock(lock_key):
    """Release a distributed lock"""
    cache.delete(lock_key)


# ============================================================================
# EMAIL DATA PREPARATION (Shared logic - computed once per execution)
# ============================================================================

def prepare_email_data(execution_id):
    """
    Prepare all email data for an execution.
    This is computed once and shared across all email recipients.
    Returns dict with all necessary data or None if execution not found.
    """
    logger.debug(f"[Email Prep] Preparing data for execution {execution_id}")
    
    try:
        execution = TestSuiteExecution.objects.select_related(
            'test_suite', 'device_group', 'created_by'
        ).get(pk=execution_id)
    except TestSuiteExecution.DoesNotExist:
        logger.error(f"[Email Prep] Execution {execution_id} not found")
        return None
    
    # Get related data
    execution_devices = TestSuiteExecutionDevice.objects.filter(
        test_suite_execution=execution
    ).select_related('device')
    
    test_cases = TestCaseExecution.objects.filter(
        test_suite_execution=execution
    ).select_related('device', 'test_case').order_by('device__name', 'execution_order')
    
    # Calculate statistics
    total_tests = test_cases.count()
    passed_tests = test_cases.filter(status='success').count()
    failed_tests = test_cases.filter(status='failed').count()
    
    # Time calculations
    start_time = execution.execution_start_time or execution.created
    end_time = timezone.now()
    completed_times = [d.completed_at for d in execution_devices if d.completed_at]
    if completed_times:
        end_time = max(completed_times)
    
    formatted_duration = format_duration(start_time, end_time)
    
    # Device statistics
    base_url = OPENWISP_SERVER_IP.rstrip('/')
    device_stats = []
    
    for dev_exec in execution_devices:
        dev_cases = test_cases.filter(device=dev_exec.device)
        d_pass = dev_cases.filter(status='success').count()
        d_total = dev_cases.count()
        
        report_url = None
        if dev_exec.allure_report_path:
            media_path = dev_exec.allure_report_path.lstrip('/')
            report_url = f"{base_url}{MEDIA_URL}{media_path}"
        
        device_stats.append({
            'name': dev_exec.device.name,
            'status': dev_exec.status,
            'passed': d_pass,
            'total': d_total,
            'report_url': report_url
        })
    
    # Generate CSV content
    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer)
    
    writer.writerow([
        'Execution ID', 'Execution Name', 'Device Name', 'Test Case ID',
        'Test Case Name', 'Test Type', 'Status', 'Exit Code',
        'Duration (s)', 'Error Message', 'Stdout', 'Stderr', 'Allure Report URL'
    ])
    
    for tc in test_cases:
        dev_exec = next((d for d in execution_devices if d.device_id == tc.device_id), None)
        allure_link = ""
        if dev_exec and dev_exec.allure_report_path:
            media_path = dev_exec.allure_report_path.lstrip('/')
            allure_link = f"{base_url}{MEDIA_URL}{media_path}"
        
        duration_sec = tc.execution_duration.total_seconds() if tc.execution_duration else ""
        std_out_safe = (tc.stdout[:5000] if tc.stdout else "")
        std_err_safe = (tc.stderr[:5000] if tc.stderr else "")
        
        writer.writerow([
            str(execution.id), execution.name, tc.device.name, tc.test_case.test_case_id,
            tc.test_case.name, tc.test_case.get_test_type_display(), tc.get_status_display(),
            tc.exit_code, duration_sec, tc.error_message, std_out_safe, std_err_safe, allure_link
        ])
    
    csv_content = csv_buffer.getvalue()
    
    # Prepare context for HTML template
    history_url = f"{base_url}/admin/test_management/testsuiteexecution/{execution.id}/history/"
    
    status_display = "Completed"
    if hasattr(execution, 'get_execution_status_display'):
        try:
            status_display = execution.get_execution_status_display()
        except Exception:
            pass
    
    context = {
        'execution_name': execution.name,
        'start_time': start_time.strftime("%Y-%m-%d %H:%M:%S"),
        'duration': formatted_duration,
        'total_devices': execution.device_count,
        'total_tests': total_tests,
        'passed_count': passed_tests,
        'failed_count': failed_tests,
        'device_stats': device_stats,
        'history_url': history_url,
        'current_year': timezone.now().year,
        'logo_url': f"{base_url}/static/test_management/logo.png"
    }
    
    logger.debug(f"[Email Prep] Data prepared successfully for execution {execution_id}")
    
    return {
        'execution_id': str(execution.id),
        'execution_name': execution.name,
        'status_display': status_display,
        'context': context,
        'csv_content': csv_content,
        'csv_filename': f"Report_{execution.name}_{datetime.now().strftime('%Y%m%d')}.csv"
    }


# ============================================================================
# MAIN EMAIL ORCHESTRATION TASK
# ============================================================================

@shared_task(bind=True, max_retries=1, soft_time_limit=120, time_limit=180)
def send_execution_completed_email(self, execution_id, created_by_id=None):
    """
    Main orchestration task - creates email logs and dispatches individual email tasks.
    This task:
    1. Validates execution exists and needs emails
    2. Creates ExecutionEmailLog entries for each recipient
    3. Dispatches individual email tasks in batches
    """
    task_id = self.request.id
    logger.info(f"[Task {task_id}] 📧 Starting email orchestration for Execution: {execution_id}")
    
    lock_key = get_execution_lock_key(execution_id)
    
    # Acquire lock to prevent duplicate processing
    if not acquire_lock(lock_key):
        logger.warning(f"[Task {task_id}] Execution {execution_id} is already being processed. Skipping.")
        return {"status": "skipped", "reason": "already_processing"}
    
    try:
        # Validate execution
        try:
            execution = TestSuiteExecution.objects.get(pk=execution_id)
        except TestSuiteExecution.DoesNotExist:
            logger.error(f"[Task {task_id}] Execution {execution_id} not found")
            return {"status": "error", "reason": "execution_not_found"}
        
        # Check if already completed
        if execution.completion_email_sent:
            logger.info(f"[Task {task_id}] Emails already sent for execution {execution_id}. Skipping.")
            return {"status": "skipped", "reason": "already_sent"}
        
        # Parse email addresses
        notification_emails = execution.notification_emails or ""
        emails_list = [e.strip().lower() for e in notification_emails.split(",") if e.strip()]
        
        if not emails_list:
            logger.warning(f"[Task {task_id}] No notification emails configured for execution {execution_id}")
            return {"status": "skipped", "reason": "no_emails"}
        
        # Remove duplicates while preserving order
        emails_list = list(dict.fromkeys(emails_list))
        
        logger.info(f"[Task {task_id}] Processing {len(emails_list)} unique emails for execution {execution_id}")
        
        # Create or get email log entries
        email_logs_created = 0
        email_logs_existing = 0
        
        for email in emails_list:
            log, created = ExecutionEmailLog.objects.get_or_create(
                execution=execution,
                email_address=email,
                defaults={
                    'status': ExecutionEmailLog.EmailStatus.PENDING,
                }
            )
            if created:
                email_logs_created += 1
            else:
                email_logs_existing += 1
        
        logger.debug(f"[Task {task_id}] Email logs - Created: {email_logs_created}, Existing: {email_logs_existing}")
        
        # Get pending emails that need to be sent
        pending_logs = ExecutionEmailLog.objects.filter(
            execution=execution,
            status__in=[
                ExecutionEmailLog.EmailStatus.PENDING,
                ExecutionEmailLog.EmailStatus.RETRY
            ]
        ).values_list('email_address', flat=True)
        
        pending_emails = list(pending_logs)
        
        if not pending_emails:
            logger.info(f"[Task {task_id}] No pending emails to send for execution {execution_id}")
            # Check if all sent successfully
            all_sent = not ExecutionEmailLog.objects.filter(
                execution=execution,
                status=ExecutionEmailLog.EmailStatus.FAILED
            ).exists()
            if all_sent:
                execution.completion_email_sent = True
                execution.save(update_fields=['completion_email_sent'])
            return {"status": "completed", "reason": "no_pending"}
        
        logger.info(f"[Task {task_id}] Dispatching {len(pending_emails)} email tasks")
        
        # Dispatch individual email tasks in batches
        batch_count = 0
        for i in range(0, len(pending_emails), EMAIL_BATCH_SIZE):
            batch = pending_emails[i:i + EMAIL_BATCH_SIZE]
            batch_count += 1
            
            for email in batch:
                # Update status to QUEUED
                ExecutionEmailLog.objects.filter(
                    execution=execution,
                    email_address=email
                ).update(status=ExecutionEmailLog.EmailStatus.QUEUED)
                
                # Dispatch individual email task with countdown for rate limiting
                countdown = (batch_count - 1) * 6  # 6 seconds between batches
                task = send_single_execution_email.apply_async(
                    args=[str(execution_id), email],
                    countdown=countdown
                )
                
                # Store task ID
                ExecutionEmailLog.objects.filter(
                    execution=execution,
                    email_address=email
                ).update(celery_task_id=task.id)
        
        logger.info(f"[Task {task_id}] ✅ Dispatched {len(pending_emails)} emails in {batch_count} batches")
        
        return {
            "status": "dispatched",
            "total_emails": len(pending_emails),
            "batches": batch_count
        }
        
    except Exception as e:
        logger.exception(f"[Task {task_id}] ❌ Failed to orchestrate emails: {str(e)}")
        raise
    
    finally:
        release_lock(lock_key)


# ============================================================================
# INDIVIDUAL EMAIL SEND TASK
# ============================================================================

@shared_task(
    bind=True,
    max_retries=EMAIL_MAX_RETRIES,
    soft_time_limit=60,
    time_limit=90,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True
)
def send_single_execution_email(self, execution_id, email_address):
    """
    Send a single email for an execution to one recipient.
    This task handles:
    1. Email lock to prevent duplicates
    2. Preparing email content (cached)
    3. Sending the email
    4. Updating email log status
    """
    task_id = self.request.id
    logger.info(f"[Task {task_id}] 📨 Sending email to {email_address} for execution {execution_id}")
    
    # Acquire lock for this specific email
    lock_key = get_email_lock_key(execution_id, email_address)
    if not acquire_lock(lock_key, timeout=120):
        logger.warning(f"[Task {task_id}] Email {email_address} is being processed. Skipping.")
        return {"status": "skipped", "reason": "locked"}
    
    try:
        # Get or create email log
        try:
            email_log = ExecutionEmailLog.objects.get(
                execution_id=execution_id,
                email_address=email_address
            )
        except ExecutionEmailLog.DoesNotExist:
            logger.error(f"[Task {task_id}] Email log not found for {email_address}")
            return {"status": "error", "reason": "log_not_found"}
        
        # Check if already sent
        if email_log.status == ExecutionEmailLog.EmailStatus.SENT:
            logger.info(f"[Task {task_id}] Email already sent to {email_address}")
            return {"status": "skipped", "reason": "already_sent"}
        
        # Update attempt count and status
        email_log.attempt_count += 1
        email_log.last_attempt_at = timezone.now()
        email_log.status = ExecutionEmailLog.EmailStatus.QUEUED
        email_log.celery_task_id = task_id
        email_log.save(update_fields=['attempt_count', 'last_attempt_at', 'status', 'celery_task_id'])
        
        logger.debug(f"[Task {task_id}] Attempt #{email_log.attempt_count} for {email_address}")
        
        # Prepare email data (use cache to avoid repeated DB queries for same execution)
        cache_key = f"email_data_{execution_id}"
        email_data = cache.get(cache_key)
        
        if not email_data:
            logger.debug(f"[Task {task_id}] Cache miss - preparing email data")
            email_data = prepare_email_data(execution_id)
            if email_data:
                cache.set(cache_key, email_data, timeout=600)  # Cache for 10 minutes
        else:
            logger.debug(f"[Task {task_id}] Cache hit - using cached email data")
        
        if not email_data:
            email_log.status = ExecutionEmailLog.EmailStatus.FAILED
            email_log.error_message = "Failed to prepare email data - execution not found"
            email_log.save(update_fields=['status', 'error_message'])
            return {"status": "error", "reason": "data_preparation_failed"}
        
        # Validate template
        template_name = 'email/execution_report_email.html'
        try:
            get_template(template_name)
        except TemplateDoesNotExist:
            error_msg = f"Template not found: {template_name}"
            logger.error(f"[Task {task_id}] {error_msg}")
            email_log.status = ExecutionEmailLog.EmailStatus.FAILED
            email_log.error_message = error_msg
            email_log.save(update_fields=['status', 'error_message'])
            return {"status": "error", "reason": "template_not_found"}
        
        # Render HTML content
        try:
            html_content = render_to_string(template_name, email_data['context'])
        except Exception as e:
            error_msg = f"Template rendering failed: {str(e)}"
            logger.error(f"[Task {task_id}] {error_msg}")
            email_log.status = ExecutionEmailLog.EmailStatus.FAILED
            email_log.error_message = error_msg
            email_log.save(update_fields=['status', 'error_message'])
            raise
        
        # Construct subject
        subject = f"Execution Report: {email_data['execution_name']} - {email_data['status_display']}"
        
        # Create and send email
        try:
            email = EmailMultiAlternatives(
                subject=subject,
                body="Please view this email in an HTML compatible client.",
                from_email=EMAIL_HOST_USER,
                to=[email_address]
            )
            email.attach_alternative(html_content, "text/html")
            email.attach(
                email_data['csv_filename'],
                email_data['csv_content'],
                'text/csv'
            )
            
            email.send(fail_silently=False)
            
            # Success - update log
            email_log.status = ExecutionEmailLog.EmailStatus.SENT
            email_log.sent_at = timezone.now()
            email_log.error_message = ""
            email_log.save(update_fields=['status', 'sent_at', 'error_message'])
            
            logger.info(f"[Task {task_id}] ✅ Email sent successfully to {email_address}")
            
            # Check if all emails for this execution are now sent
            check_and_update_execution_email_status.delay(execution_id)
            
            return {"status": "sent", "email": email_address}
            
        except Exception as e:
            error_msg = f"SMTP send failed: {str(e)}"
            logger.error(f"[Task {task_id}] {error_msg}")
            
            # Determine if we should retry
            if self.request.retries < EMAIL_MAX_RETRIES:
                email_log.status = ExecutionEmailLog.EmailStatus.RETRY
                email_log.error_message = error_msg
                email_log.save(update_fields=['status', 'error_message'])
                raise  # Re-raise to trigger Celery retry
            else:
                email_log.status = ExecutionEmailLog.EmailStatus.FAILED
                email_log.error_message = f"Failed after {EMAIL_MAX_RETRIES} attempts: {error_msg}"
                email_log.save(update_fields=['status', 'error_message'])
                return {"status": "failed", "error": error_msg}
            
    except Exception as e:
        logger.exception(f"[Task {task_id}] ❌ Unexpected error sending to {email_address}: {str(e)}")
        raise
    
    finally:
        release_lock(lock_key)


# ============================================================================
# STATUS CHECK TASK
# ============================================================================

@shared_task(bind=True, max_retries=3)
def check_and_update_execution_email_status(self, execution_id):
    """
    Check if all emails for an execution have been sent and update the flag.
    Called after each successful email send.
    """
    task_id = self.request.id
    logger.debug(f"[Task {task_id}] Checking email completion for execution {execution_id}")
    
    try:
        execution = TestSuiteExecution.objects.get(pk=execution_id)
        
        # Already marked as complete
        if execution.completion_email_sent:
            return {"status": "already_complete"}
        
        # Check email log status
        total_logs = ExecutionEmailLog.objects.filter(execution=execution).count()
        
        if total_logs == 0:
            logger.warning(f"[Task {task_id}] No email logs found for execution {execution_id}")
            return {"status": "no_logs"}
        
        sent_count = ExecutionEmailLog.objects.filter(
            execution=execution,
            status=ExecutionEmailLog.EmailStatus.SENT
        ).count()
        
        pending_count = ExecutionEmailLog.objects.filter(
            execution=execution,
            status__in=[
                ExecutionEmailLog.EmailStatus.PENDING,
                ExecutionEmailLog.EmailStatus.QUEUED,
                ExecutionEmailLog.EmailStatus.RETRY
            ]
        ).count()
        
        failed_count = ExecutionEmailLog.objects.filter(
            execution=execution,
            status=ExecutionEmailLog.EmailStatus.FAILED
        ).count()
        
        logger.debug(
            f"[Task {task_id}] Email status for {execution_id}: "
            f"Total={total_logs}, Sent={sent_count}, Pending={pending_count}, Failed={failed_count}"
        )
        
        # If no more pending, mark as complete (even if some failed)
        if pending_count == 0:
            execution.completion_email_sent = True
            execution.save(update_fields=['completion_email_sent'])
            
            logger.info(
                f"[Task {task_id}] ✅ Execution {execution_id} email completion marked. "
                f"Sent: {sent_count}, Failed: {failed_count}"
            )
            
            return {
                "status": "completed",
                "sent": sent_count,
                "failed": failed_count
            }
        
        return {
            "status": "in_progress",
            "sent": sent_count,
            "pending": pending_count,
            "failed": failed_count
        }
        
    except TestSuiteExecution.DoesNotExist:
        logger.error(f"[Task {task_id}] Execution {execution_id} not found")
        return {"status": "error", "reason": "not_found"}
    except Exception as e:
        logger.exception(f"[Task {task_id}] Error checking email status: {str(e)}")
        raise


# ============================================================================
# RETRY FAILED EMAILS TASK
# ============================================================================

@shared_task(bind=True)
def retry_failed_emails(self, execution_id=None, max_age_hours=24):
    """
    Retry failed emails for a specific execution or all recent executions.
    Can be called manually or scheduled as a periodic task.
    """
    task_id = self.request.id
    logger.info(f"[Task {task_id}] 🔄 Retrying failed emails")
    
    cutoff_time = timezone.now() - timedelta(hours=max_age_hours)
    
    # Build query
    query = ExecutionEmailLog.objects.filter(
        status=ExecutionEmailLog.EmailStatus.FAILED,
        attempt_count__lt=EMAIL_MAX_RETRIES,
        last_attempt_at__gte=cutoff_time
    )
    
    if execution_id:
        query = query.filter(execution_id=execution_id)
    
    failed_logs = list(query.select_related('execution'))
    
    if not failed_logs:
        logger.info(f"[Task {task_id}] No failed emails to retry")
        return {"status": "no_retries", "count": 0}
    
    logger.info(f"[Task {task_id}] Found {len(failed_logs)} failed emails to retry")
    
    retried_count = 0
    for log in failed_logs:
        log.status = ExecutionEmailLog.EmailStatus.RETRY
        log.save(update_fields=['status'])
        
        send_single_execution_email.apply_async(
            args=[str(log.execution_id), log.email_address],
            countdown=retried_count * 2  # Stagger retries
        )
        retried_count += 1
    
    logger.info(f"[Task {task_id}] ✅ Queued {retried_count} emails for retry")
    
    return {"status": "retried", "count": retried_count}


# ============================================================================
# CLEANUP TASK
# ============================================================================

@shared_task(bind=True)
def cleanup_old_email_logs(self, days_to_keep=30):
    """
    Clean up old email logs to prevent database bloat.
    Schedule this as a periodic task (e.g., weekly).
    """
    task_id = self.request.id
    logger.info(f"[Task {task_id}] 🧹 Cleaning up email logs older than {days_to_keep} days")
    
    cutoff_date = timezone.now() - timedelta(days=days_to_keep)
    
    deleted_count, _ = ExecutionEmailLog.objects.filter(
        created__lt=cutoff_date,
        status=ExecutionEmailLog.EmailStatus.SENT  # Only delete successful ones
    ).delete()
    
    logger.info(f"[Task {task_id}] ✅ Deleted {deleted_count} old email logs")
    
    return {"status": "cleaned", "deleted": deleted_count}


# ============================================================================
# BULK EMAIL TASK (For 50+ executions scenario)
# ============================================================================

@shared_task(bind=True, soft_time_limit=300, time_limit=360)
def send_bulk_execution_emails(self, execution_ids):
    """
    Handle bulk email sending for multiple executions.
    Use this when you have 50+ executions to process.
    """
    task_id = self.request.id
    logger.info(f"[Task {task_id}] 📧 Starting bulk email for {len(execution_ids)} executions")
    
    results = {
        'total': len(execution_ids),
        'dispatched': 0,
        'skipped': 0,
        'errors': 0
    }
    
    for i, exec_id in enumerate(execution_ids):
        try:
            # Stagger execution to avoid overwhelming the system
            countdown = i * 2  # 2 seconds between each execution
            
            send_execution_completed_email.apply_async(
                args=[str(exec_id)],
                countdown=countdown
            )
            results['dispatched'] += 1
            
        except Exception as e:
            logger.error(f"[Task {task_id}] Failed to dispatch for execution {exec_id}: {str(e)}")
            results['errors'] += 1
    
    logger.info(
        f"[Task {task_id}] ✅ Bulk dispatch complete: "
        f"Dispatched={results['dispatched']}, Errors={results['errors']}"
    )
    
    return results
