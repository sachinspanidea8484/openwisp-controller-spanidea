import logging
from celery import shared_task

logger = logging.getLogger(__name__)

MEASUREMENT_NAME = 'test_case_execution_logs'


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 5},
    ignore_result=True,
)
def write_test_execution_to_influxdb(self, test_case_execution_id):
    """
    Writes terminal-state TestCaseExecution data to InfluxDB for archival.
    Triggered only when status changes to a terminal state.
    """
    from openwisp_monitoring.db import timeseries_db
    from openwisp_monitoring.db.exceptions import TimeseriesWriteException
    from .swapper import load_model

    TestCaseExecution = load_model('TestCaseExecution')

    try:
        tce = (
            TestCaseExecution.objects
            .select_related('test_case', 'device', 'test_suite_execution')
            .get(pk=test_case_execution_id)
        )
    except TestCaseExecution.DoesNotExist:
        logger.warning(
            f'[InfluxDB] TestCaseExecution {test_case_execution_id} not found, skipping.'
        )
        return

    # Tags — low cardinality identifiers used for filtering in InfluxDB
    tags = {
        'device_id':            str(tce.device_id),
        'device_name':          tce.device.name,
        'test_case_id':         str(tce.test_case.test_case_id),
        'test_case_name':       tce.test_case.name,
        'execution_name':       tce.test_suite_execution.name,
        'status':               tce.status,
        'test_execution_id':    str(tce.test_suite_execution_id),
        'test_case_execution_id':  str(tce.pk),  
    }

    # Fields — the actual payload stored in InfluxDB
    values = {
        # Numeric fields (required — InfluxDB needs at least one field)
        'exit_code':            tce.exit_code if tce.exit_code is not None else -1,
        'execution_order':      tce.execution_order,
        'retry_count':          tce.retry_count,
        'duration_seconds': (
            tce.execution_duration.total_seconds()
            if tce.execution_duration is not None
            else 0.0
        ),
        # Text fields for log archival
        'stdout':               tce.stdout or '',
        'stderr':               tce.stderr or '',
        'error_message':        tce.error_message or '',
    }

    # Use completed_at as the datapoint timestamp so it's meaningful in time-series
    # Fall back to now() if not set
    from django.utils.timezone import now
    timestamp = tce.completed_at or now()

    try:
        timeseries_db.write(
            MEASUREMENT_NAME,
            values,
            tags=tags,
            timestamp=timestamp.isoformat(),
        )
        logger.info(
            f'[InfluxDB] Written execution log for TestCaseExecution {test_case_execution_id} '
            f'(device={tce.device.name}, test_case={tce.test_case.test_case_id}, status={tce.status})'
        )
    except TimeseriesWriteException as exc:
        logger.error(
            f'[InfluxDB] Failed to write TestCaseExecution {test_case_execution_id}: {exc}'
        )
        raise  # triggers celery autoretry