from asgiref.sync import sync_to_async, async_to_sync
from django.contrib.auth import get_user_model
from openwisp_notifications.signals import notify
from swapper import load_model

User = get_user_model()
TestSuiteExecution = load_model("test_management", "TestSuiteExecution")



from .tasks import send_execution_completed_notification


def testsuite_execution_status_notification(sender, instance, created, **kwargs):
    # Just enqueue task
    if instance.execution_status== 3 : 
        send_execution_completed_notification.delay(
            instance.pk,
            instance.created_by_id,
        )