from . import settings as app_settings


def controller_api_settings(request):
    return {
        "OPENWISP_CONTROLLER_API_HOST": app_settings.OPENWISP_CONTROLLER_API_HOST,
        "EXECUTION_HISTORY_REFRESH_INTERVAL" : app_settings.EXECUTION_HISTORY_REFRESH_INTERVAL,
    }
