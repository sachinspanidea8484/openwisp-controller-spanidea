from datetime import timedelta

from django.apps import AppConfig
from django.db import models
from django.db.models import Count, Sum
from django.db.models.functions import Cast, Round
from django.db.models.signals import post_save
from django.utils.translation import gettext_lazy as _
from openwisp_monitoring.monitoring.configuration import (
    _register_chart_configuration_choice,
    register_metric,
)
from swapper import load_model

from openwisp_utils.admin_theme import register_dashboard_chart

from .utils import (
    get_datetime_filter_start_datetime,
    get_datetime_filter_stop_datetime,
    get_utc_datetime_from_local_date,
)


class OpenwispRadiusMonitoringConfig(AppConfig):
    name = "openwisp_radius.integrations.monitoring"
    label = "openwisp_radius_monitoring"
    verbose_name = _("OpenWISP RADIUS Monitoring")

    def ready(self):
        super().ready()
        self.register_dashboard_charts()
        self.register_radius_metrics()
        self.connect_signal_receivers()

    def register_dashboard_charts(self):
        register_dashboard_chart(
            position=30,
            config={
                "name": _("Today's RADIUS sessions"),
                "query_params": {
                    "app_label": "openwisp_radius",
                    "model": "radiusaccounting",
                    "filter": {
                        # This will filter the sessions for today
                        "start_time__gte": get_utc_datetime_from_local_date,
                        "start_time__lt": lambda: get_utc_datetime_from_local_date()
                        + timedelta(days=1),
                    },
                    "aggregate": {
                        "open": Count(
                            "session_id", filter=models.Q(stop_time__isnull=True)
                        ),
                        "closed": Count(
                            "session_id", filter=models.Q(stop_time__isnull=False)
                        ),
                    },
                },
                "colors": {
                    "open": "#267126",
                    "closed": "#a72d1d",
                },
                "filters": {
                    "key": "stop_time__isnull",
                    "open": "True",
                    "closed": "False",
                },
                "main_filters": {
                    "start_time__gte": get_datetime_filter_start_datetime,
                    "start_time__lt": get_datetime_filter_stop_datetime,
                },
                "labels": {
                    "open": "Open",
                    "closed": "Closed",
                },
            },
        )
        register_dashboard_chart(
            position=31,
            config={
                "name": _("Today's RADIUS traffic (GB)"),
                "query_params": {
                    "app_label": "openwisp_radius",
                    "model": "radiusaccounting",
                    "filter": {
                        # This will filter the sessions for today
                        "start_time__gte": get_utc_datetime_from_local_date,
                        "start_time__lt": lambda: get_utc_datetime_from_local_date()
                        + timedelta(days=1),
                    },
                    "aggregate": {
                        "download_traffic": Round(
                            Cast(Sum("input_octets"), models.FloatField()) / 10**9
                        ),
                        "upload_traffic": Round(
                            Cast(Sum("output_octets"), models.FloatField()) / 10**9
                        ),
                    },
                },
                "colors": {
                    "download_traffic": "#1f77b4",
                    "upload_traffic": "#ff7f0e",
                },
                "labels": {
                    "download_traffic": "Download traffic (GB)",
                    "upload_traffic": "Upload traffic (GB)",
                },
                "main_filters": {
                    "start_time__gte": get_datetime_filter_start_datetime,
                    "start_time__lt": get_datetime_filter_stop_datetime,
                },
                "filtering": "False",
            },
        )

    def register_radius_metrics(self):
        from .configuration import RADIUS_METRICS

        for metric_key, metric_config in RADIUS_METRICS.items():
            register_metric(metric_key, metric_config)
            for chart_key, chart_config in metric_config.get("charts", {}).items():
                _register_chart_configuration_choice(chart_key, chart_config)

    def connect_signal_receivers(self):
        from .receivers import post_save_radiusaccounting

        RadiusAccounting = load_model("openwisp_radius", "RadiusAccounting")

        post_save.connect(
            post_save_radiusaccounting,
            sender=RadiusAccounting,
            dispatch_uid="post_save_radiusaccounting_radius_acc_metric",
        )
