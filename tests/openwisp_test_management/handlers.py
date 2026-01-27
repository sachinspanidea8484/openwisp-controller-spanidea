# handlers.py
import logging
from django.contrib.auth import get_user_model
from swapper import load_model

logger = logging.getLogger(__name__)

User = get_user_model()
TestSuiteExecution = load_model("test_management", "TestSuiteExecution")


def testsuite_execution_status_notification(sender, instance, created, **kwargs):
    """
    Signal handler for TestSuiteExecution status changes.
    Triggers email notification when execution is completed (status == 3).
    """
    from .tasks import send_execution_completed_email ,send_execution_completed_notification

    f">>>>>>>>>>>>>> notification emails for execution {instance.pk}." ,

    
    # Only trigger for completed executions
    if instance.execution_status != 3:
        return
    
    if instance.execution_status== 3 : 
        send_execution_completed_notification.delay(
            instance.pk,
            instance.created_by_id,
        )
    
    # Skip if no notification emails configured
    if not instance.notification_emails:
        logger.debug(
            f"[Handler] No notification emails for execution {instance.pk}. Skipping."
        )
        return
    
    # Skip if already sent
    if instance.completion_email_sent:
        logger.debug(
            f"[Handler] Emails already sent for execution {instance.pk}. Skipping."
        )
        return
    
    logger.info(
        f"[Handler] Execution {instance.pk} completed. "
        f"Dispatching email task to: {instance.notification_emails}"
    )
    
    # Dispatch email task asynchronously
    try:
        send_execution_completed_email.delay(
            str(instance.pk),
            instance.created_by_id
        )
    except Exception as e:
        logger.exception(
            f"[Handler] Failed to dispatch email task for execution {instance.pk}: {str(e)}"
        )