import os
import zipfile
from django.conf import settings
from django.db.models.signals import post_save , pre_save
from django.dispatch import receiver
from .models import TestCase
from .settings import EXECUTOR_SERVER_IP ,OPENWISP_SERVER_IP ,MEDIA_URL
import requests

import logging

logger = logging.getLogger(__name__)

@receiver(pre_save, sender=TestCase)
def capture_old_testcase_data(sender, instance, **kwargs):
    """Capture old values before save to detect changes"""
    if not instance.pk:
        # New instance - mark that files need to be pushed
        instance._is_new = True
        instance._needs_push = True
        return
    
    # Get old values from database
    try:
        old = sender.objects.get(pk=instance.pk)
        instance._old_test_case_id = old.test_case_id
        instance._old_python_script = old.python_script.name if old.python_script else None
        instance._old_robot_script = old.robot_script.name if old.robot_script else None
        instance._is_new = False
        
        # Detect changes
        test_case_id_changed = old.test_case_id != instance.test_case_id
        python_changed = (old.python_script.name if old.python_script else None) != (instance.python_script.name if instance.python_script else None)
        robot_changed = (old.robot_script.name if old.robot_script else None) != (instance.robot_script.name if instance.robot_script else None)
        
        # Mark if push needed
        instance._needs_push = test_case_id_changed or python_changed or robot_changed
        instance._test_case_id_changed = test_case_id_changed
        instance._python_changed = python_changed
        instance._robot_changed = robot_changed
        
        if instance._needs_push:
            print(f"[DEBUG] Changes detected:")
            print(f"  - Test Case ID changed: {test_case_id_changed}")
            print(f"  - Python script changed: {python_changed}")
            print(f"  - Robot script changed: {robot_changed}")
            
    except sender.DoesNotExist:
        instance._is_new = True
        instance._needs_push = True


@receiver(post_save, sender=TestCase)
def robot_framework_server_push(sender, instance, created, **kwargs):
    """Push robot and python files to executor server when test case is saved"""

    
    # Only push for Robot Framework test type
    if instance.test_type != 1:  # Assuming 1 = ROBOT_FRAMEWORK
        return
    
    # Check if push is needed
    needs_push = getattr(instance, '_needs_push', False)
    is_new = getattr(instance, '_is_new', False)
    
    if not needs_push:
        print(f"[DEBUG] No changes detected for {instance.test_case_id}, skipping push")
        return
    
    try:
        if is_new:
            print(f"[DEBUG] NEW test case - Starting file push: {instance.test_case_id}")
        else:
            print(f"[DEBUG] EDIT test case - Starting file push: {instance.test_case_id}")
        
        # Prepare file URLs
        robot_file_url = None
        python_file_url = None
        
        if instance.robot_script:
            robot_file_url = build_absolute_file_url(instance.robot_script.name)
            print(f"[DEBUG] Robot file URL: {robot_file_url}")
        
        if instance.python_script:
            python_file_url = build_absolute_file_url(instance.python_script.name)
            print(f"[DEBUG] Python file URL: {python_file_url}")
        
        # Get change information
        test_case_id_changed = getattr(instance, '_test_case_id_changed', False)
        python_changed = getattr(instance, '_python_changed', False)
        robot_changed = getattr(instance, '_robot_changed', False)
        old_test_case_id = getattr(instance, '_old_test_case_id', None)
        
        # Build API payload
        api_payload = {
            "test_case_id": instance.test_case_id,
            "test_case_name": instance.name,
            "category": instance.category.name if instance.category else None,
            "robot_script_url": robot_file_url,
            "python_script_url": python_file_url,
            "test_type": instance.get_test_type_display(),
            "description": instance.description or "",
            "params": instance.params or {},
            "is_active": instance.is_active,
            
            # **NEW: Add operation type and change details**
            "operation": "create" if is_new else "update",
            "changes": {
                "test_case_id_changed": test_case_id_changed,
                "old_test_case_id": old_test_case_id,
                "python_script_changed": python_changed,
                "robot_script_changed": robot_changed,
            }
        }
        
        # Call executor server API
        push_to_executor_server(api_payload, instance)
        
    except Exception as e:
        logger.error(f"Error pushing files to executor server: {str(e)}")
        print(f"[DEBUG] ❌ Error pushing files: {str(e)}")
        
        # Update push status to failed
        TestCase.objects.filter(pk=instance.pk).update(
            script_push_status='failed',
        )


def build_absolute_file_url(file_path):
    """
    Build absolute URL for file download
    Args:
        file_path: Relative path like "test_scripts/BB-001.py"
    Returns:
        Absolute URL like "http://openwisp-server.com/media/test_scripts/BB-001.py"
    """
    from django.conf import settings
    
    # Get MEDIA_URL (e.g., "/media/")
    media_url = MEDIA_URL
    
    # Build full URL path
    file_download_url = f"{media_url}{file_path}"
    
    # Make absolute if relative
    if not file_download_url.startswith('http'):
        # Get base URL from settings
        base_url = OPENWISP_SERVER_IP
        # Remove trailing slash from base_url if exists
        base_url = base_url.rstrip('/')
        file_download_url = f"{base_url}{file_download_url}"
    
    return file_download_url


def push_to_executor_server(api_payload, instance):
    """
    Push test case files to executor server via API
    """
    from django.conf import settings
    from django.utils import timezone
    
    executor_api_url = EXECUTOR_SERVER_IP + "/api/v1/push-test-case"
    
    try:
        print(f"[DEBUG] Sending request to executor server: {executor_api_url}")
        print(f"[DEBUG] Operation: {api_payload['operation']}")
        print(f"[DEBUG] Changes: {api_payload['changes']}")
        return
        
        response = requests.post(
            executor_api_url,
            json=api_payload,
            timeout=60,
            headers={'Content-Type': 'application/json'}
        )
        
        print(f"\n[DEBUG] API Response:")
        print(f"[DEBUG] Status Code: {response.status_code}")
        
        try:
            response_json = response.json()
            print(f"[DEBUG] Response Body: {response_json}")
        except:
            print(f"[DEBUG] Response Body (text): {response.text[:500]}")
        
        if response.status_code in [200, 201]:
            logger.info(f"Test case {api_payload['test_case_id']} pushed successfully")
            print(f"[DEBUG] ✅ Push successful!")
            
            # Update push status in database
            TestCase.objects.filter(pk=instance.pk).update(
                script_push_status='success',
            )
            
        else:
            logger.error(f"Executor API failed: {response.status_code} - {response.text}")
            print(f"[DEBUG] ❌ Push failed! Status: {response.status_code}")
            
            # Update push status to failed
            TestCase.objects.filter(pk=instance.pk).update(
                script_push_status='failed',
            )
            
    except requests.exceptions.Timeout:
        logger.error(f"Executor API timeout for test case {api_payload['test_case_id']}")
        print(f"[DEBUG] ❌ API call timed out!")
        
        TestCase.objects.filter(pk=instance.pk).update(
            script_push_status='failed',
        )
        
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Cannot connect to executor server: {str(e)}")
        print(f"[DEBUG] ❌ Connection error: {str(e)}")
        
        TestCase.objects.filter(pk=instance.pk).update(
            script_push_status='failed',
        )
        
    except Exception as e:
        logger.error(f"Unexpected error pushing to executor: {str(e)}")
        print(f"[DEBUG] ❌ Unexpected error: {str(e)}")
        
        TestCase.objects.filter(pk=instance.pk).update(
            script_push_status='failed',
        )



@receiver(post_save, sender=TestCase)
def handle_id_and_file_changes(sender, instance, created, **kwargs):
    """Rename files when test case ID changes"""
    if created:
        return

    old_id = getattr(instance, "_old_test_case_id", None)
    new_id = instance.test_case_id

    if not old_id or old_id == new_id:
        return

    base_path = settings.MEDIA_ROOT

    for field in ("python_script", "robot_script"):
        file_field = getattr(instance, field)

        if not file_field:
            continue

        # File was replaced → DO NOTHING
        if file_field._file is not None and not file_field._committed:
            continue

        old_rel_path = file_field.name
        dir_name = os.path.dirname(old_rel_path)
        ext = os.path.splitext(old_rel_path)[1]

        old_abs = os.path.join(base_path, old_rel_path)
        new_rel = os.path.join(dir_name, f"{new_id}{ext}")
        new_abs = os.path.join(base_path, new_rel)

        if os.path.exists(old_abs):
            os.rename(old_abs, new_abs)

        setattr(instance, field, new_rel)

    sender.objects.filter(pk=instance.pk).update(
        python_script=instance.python_script,
        robot_script=instance.robot_script,
    )
    
@receiver(pre_save, sender=TestCase)
def capture_old_testcase_id(sender, instance, **kwargs):
    if not instance.pk:
        return

    old = sender.objects.filter(pk=instance.pk).values("test_case_id").first()
    instance._old_test_case_id = old["test_case_id"] if old else None

