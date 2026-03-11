# admin_datetime_format.py
import datetime
from django.utils.html import format_html
from django.utils.timezone import is_naive
from django.conf import settings
from django.contrib.admin.utils import display_for_field as original_display_for_field

def custom_display_for_field(value, field, empty_value_display, **kwargs):
    if isinstance(value, datetime.datetime):
        if settings.USE_TZ and is_naive(value):
            from django.utils.timezone import utc
            value = value.replace(tzinfo=utc)
        return format_html(
            '<span class="js-datetime" data-datetime="{}"></span>',
            value.isoformat()
        )
    return original_display_for_field(value, field, empty_value_display)

def patch_admin_datetime_display():
    import django.contrib.admin.utils
    django.contrib.admin.utils.display_for_field = custom_display_for_field
