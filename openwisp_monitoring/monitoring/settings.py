from ..settings import get_settings_value

ADDITIONAL_CHARTS = get_settings_value('CHARTS', {})
ADDITIONAL_METRICS = get_settings_value('METRICS', {})



EXECUTOR_SERVER_IP = get_settings_value( "EXECUTOR_SERVER_IP", "http://172.17.0.1:8080")


OPENWISP_SERVER_IP = get_settings_value( "OPENWISP_SERVER_IP", "http://172.17.0.1:8000")


RETRY_OPTIONS = get_settings_value(
    'WRITE_RETRY_OPTIONS',
    dict(
        max_retries=None, retry_backoff=True, retry_backoff_max=600, retry_jitter=True
    ),
)
ADDITIONAL_DASHBOARD_TRAFFIC_CHART = get_settings_value('DASHBOARD_TRAFFIC_CHART', {})
