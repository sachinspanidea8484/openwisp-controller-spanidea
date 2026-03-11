import logging

from django.db.models.signals import post_save
from django.dispatch import receiver


logger = logging.getLogger(__name__)

# Terminal statuses — only write to InfluxDB when execution is finished
_TERMINAL_STATUSES = {'success', 'failed', 'timeout', 'aborted'}


def register_test_execution_signal():
    """
    Call this from your AppConfig.ready() to register the signal.
    Kept as a function to avoid import-time side effects.
    """
    from .swapper import load_model
    TestCaseExecution = load_model('TestCaseExecution')

    @receiver(post_save, sender=TestCaseExecution, weak=False)
    def on_test_case_execution_saved(sender, instance, created, update_fields, **kwargs):
        """
        Fires the InfluxDB write task only when:
        1. The record is not newly created (we want a status *change*)
        2. The status field was updated (update_fields hint respected)
        3. The new status is terminal
        """
        # If update_fields is provided and 'status' is not among them, skip
        if update_fields is not None and 'status' not in update_fields:
            return

        if instance.status not in _TERMINAL_STATUSES:
            return

        from .tasks_influxdb import write_test_execution_to_influxdb
        write_test_execution_to_influxdb.delay(str(instance.pk))
        logger.debug(
            f'[InfluxDB] Queued write for TestCaseExecution {instance.pk} '
            f'(status={instance.status})'
        )