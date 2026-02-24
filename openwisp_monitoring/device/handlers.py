import logging
from django.dispatch import receiver
from swapper import load_model

from openwisp_monitoring.monitoring.signals import threshold_crossed

logger = logging.getLogger(__name__)
Device = load_model('config', 'Device')
DeviceMonitoring = load_model('device_monitoring', 'DeviceMonitoring')


@receiver(threshold_crossed, dispatch_uid='custom_ping_status_handler')
def handle_ping_status_change(sender, metric, alert_settings, target, 
                               first_time, tolerance_crossed, **kwargs):
    """
    Custom logic when device becomes reachable/unreachable.
    
    This is triggered when the ping metric crosses the threshold.
    """
    # Only process ping metrics
    if metric.configuration != 'ping':
        return
    
    # Only process Device objects (not other types)
    if not isinstance(target, Device):
        return
    
    device = target
    
    # Get device monitoring status
    try:
        monitoring = device.monitoring
    except DeviceMonitoring.DoesNotExist:
        return
  