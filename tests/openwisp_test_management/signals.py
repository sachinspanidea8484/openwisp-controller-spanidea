import os
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
    
    # NEW OBJECT
    if not instance.pk:
        instance._is_new = True
        instance._needs_push = True
        return

    try:
        old = sender.objects.get(pk=instance.pk)

        instance._old_test_case_id = old.test_case_id
        instance._old_python_script = old.python_script.name if old.python_script else None
        instance._old_robot_script = old.robot_script.name if old.robot_script else None
        instance._is_new = False

        #  Detect test_case_id change
        test_case_id_changed = old.test_case_id != instance.test_case_id

        #  Properly detect file replacement (even if filename same)
        python_changed = False
        robot_changed = False

        # ----- Detect Python change -----
        if instance.python_script:
            # New file uploaded
            if instance.python_script._file is not None and not instance.python_script._committed:
                python_changed = True
            else:
                python_changed = (
                    (old.python_script.name if old.python_script else None)
                    !=
                    (instance.python_script.name if instance.python_script else None)
                )
        else:
            python_changed = old.python_script is not None

        # ----- Detect Robot change -----
        if instance.robot_script:
            # New file uploaded
            if instance.robot_script._file is not None and not instance.robot_script._committed:
                robot_changed = True
            else:
                robot_changed = (
                    (old.robot_script.name if old.robot_script else None)
                    !=
                    (instance.robot_script.name if instance.robot_script else None)
                )
        else:
            robot_changed = old.robot_script is not None

        # Mark if push needed
        instance._needs_push = (
            test_case_id_changed or python_changed or robot_changed
        )

        instance._test_case_id_changed = test_case_id_changed
        instance._python_changed = python_changed
        instance._robot_changed = robot_changed

        if instance._needs_push:
            logger.info(
                f"Changes detected for {instance.test_case_id} | "
                f"ID changed: {test_case_id_changed}, "
                f"Python changed: {python_changed}, "
                f"Robot changed: {robot_changed}"
            )

    except sender.DoesNotExist:
        instance._is_new = True
        instance._needs_push = True


def get_service_token(instance):
    """
    Get or create the auth token for the user who created this test case.
    """
    from rest_framework.authtoken.models import Token
 
    user = getattr(instance, 'created_by', None)
 
    if not user:
        logger.error("No created_by user found on test case instance")
        return None
 
    token, _ = Token.objects.get_or_create(user=user)
    return token.key

@receiver(post_save, sender=TestCase, dispatch_uid="push_to_executor_last")
def robot_framework_server_push(sender, instance, created, **kwargs):
    """
    PRIORITY 2: Push to executor AFTER files are renamed
    """
    print(f"file push ::")
    # Only push for Robot Framework test type
    if instance.test_type != 1:  # 1 = ROBOT_FRAMEWORK
        return
    
    # Check if push is needed
    needs_push = getattr(instance, '_needs_push', False)
    is_new = getattr(instance, '_is_new', False)
    
    if not needs_push:
        print(f"No changes detected for {instance.test_case_id}, skipping push")
        return
    
    try:
        # Reload instance to get UPDATED file paths after rename
        test_case_id_changed = getattr(instance, '_test_case_id_changed', False)
        python_changed = getattr(instance, '_python_changed', False)
        robot_changed = getattr(instance, '_robot_changed', False)
        old_test_case_id = getattr(instance, '_old_test_case_id', None)
        
        if test_case_id_changed and not python_changed and not robot_changed:
            # Files were renamed, reload from DB to get new paths
            instance.refresh_from_db()
            print(f"[DEBUG] Reloaded instance after file rename")
        
        if is_new:
            print(f"NEW test case - Starting file push: {instance.test_case_id}")
        else:
            print(f"EDIT test case - Starting file push: {instance.test_case_id}")
        
        # NOW build URLs with correct (renamed) file paths
        robot_file_url = None
        python_file_url = None
        
        if instance.robot_script:
            robot_file_url = build_absolute_file_url(instance.robot_script.name)
            print(f"Robot file URL: {robot_file_url}")
        
        if instance.python_script:
            python_file_url = build_absolute_file_url(instance.python_script.name)
            print(f"Python file URL: {python_file_url}")
        
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
        print(f"Error pushing files: {str(e)}")


def build_absolute_file_url(file_path):
    """
    Build absolute URL for file download
    """
    from django.conf import settings
    
    media_url = MEDIA_URL
    file_download_url = f"{media_url}{file_path}"
    
    if not file_download_url.startswith('http'):
        base_url = OPENWISP_SERVER_IP.rstrip('/')
        file_download_url = f"{base_url}{file_download_url}"
    
    return file_download_url



def push_to_executor_server(api_payload, instance):
    """
    Push test case files to executor server via API
    """
    from django.utils import timezone
    
    executor_api_url = EXECUTOR_SERVER_IP + "/api/v1/push-test-case"
    
    try:

        token = get_service_token(instance)
        api_payload["auth_token"] = token
        response = requests.post(
            executor_api_url,
            json=api_payload,
            timeout=60,
            headers={'Content-Type': 'application/json'}
        )
        
        print(f"\nAPI Response:")
        print(f"Status Code: {response.status_code}")
        
        try:
            response_json = response.json()
            print(f"Response Body: {response_json}")
        except:
            print(f"Response Body (text): {response.text[:500]}")
        
        if response.status_code in [200, 201]:
            logger.info(f"Test case {api_payload['test_case_id']} pushed successfully")
            print(f"Push successful!")
        else:
            logger.error(f"Executor API failed: {response.status_code} - {response.text}")
            print(f"Push failed! Status: {response.status_code}")
            
    except requests.exceptions.Timeout:
        logger.error(f"Executor API timeout for test case {api_payload['test_case_id']}")
        print(f"API call timed out!")
        
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Cannot connect to executor server: {str(e)}")
        print(f"Connection error: {str(e)}")
        
    except Exception as e:
        logger.error(f"Unexpected error pushing to executor: {str(e)}")
        print(f"Unexpected error: {str(e)}")

        
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

@receiver(post_save, sender=TestCase, dispatch_uid="rename_files_first")
def handle_id_and_file_changes(sender, instance, created, **kwargs):
    """
    PRIORITY 1: Rename files FIRST when test case ID changes
    This MUST run before robot_framework_server_push
    """
    if created:
        return

    old_id = getattr(instance, "_old_test_case_id", None)
    new_id = instance.test_case_id

    if not old_id or old_id == new_id:
        return

    base_path = settings.MEDIA_ROOT
    files_renamed = False

    for field in ("python_script", "robot_script"):
        file_field = getattr(instance, field)

        if not file_field:
            continue

        # File was replaced → DO NOTHING
        if file_field._file is not None and not file_field._committed:
            print(f"{field} was replaced with new upload, skipping rename")
            continue

        old_rel_path = file_field.name
        dir_name = os.path.dirname(old_rel_path)
        ext = os.path.splitext(old_rel_path)[1]

        old_abs = os.path.join(base_path, old_rel_path)
        new_rel = os.path.join(dir_name, f"{new_id}{ext}")
        new_abs = os.path.join(base_path, new_rel)

        if os.path.exists(old_abs):
            os.rename(old_abs, new_abs)
            print(f"Renamed {field}: {old_abs} → {new_abs}")
            setattr(instance, field, new_rel)
            files_renamed = True
        else:
            print(f"File not found: {old_abs}")

    # Update database with new file paths
    if files_renamed:
        sender.objects.filter(pk=instance.pk).update(
            python_script=instance.python_script,
            robot_script=instance.robot_script,
        )
        print(f"Database updated with new file paths")

