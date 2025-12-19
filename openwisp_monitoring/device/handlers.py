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
        logger.warning(f"No monitoring object for device {device.id}")
        return
    
    # ============================================
    # ADD YOUR CUSTOM LOGIC HERE
    # ============================================
    
    if metric.is_healthy_tolerant:
        # Device is REACHABLE / ONLINE
        logger.info("=" * 70)
        logger.info(f"✅ DEVICE ONLINE: {device.name}")
        logger.info(f"   Device ID: {device.id}")
        logger.info(f"   Status: {monitoring.status}")
        logger.info(f"   First time: {first_time}")
        logger.info("=" * 70)
        
        # YOUR CUSTOM LOGIC FOR ONLINE DEVICE
        # Examples:
        # - Send custom notification
        # - Update external system
        # - Trigger automation
        # - Log to external service
        # - Update custom database table
        
    else:
        # Device is UNREACHABLE / OFFLINE
        logger.info("=" * 70)
        logger.info(f"❌ DEVICE OFFLINE: {device.name}")
        logger.info(f"   Device ID: {device.id}")
        logger.info(f"   Status: {monitoring.status}")
        logger.info(f"   First time: {first_time}")
        logger.info("=" * 70)
        
        # YOUR CUSTOM LOGIC FOR OFFLINE DEVICE
        # Examples:
        # - Send alert to external system
        # - Create ticket in ticketing system
        # - Trigger failover
        # - Log to external service
        # - Update custom database table
    
    # Additional info available:
    # - metric.key: 'ping'
    # - metric.field_name: 'reachable'
    # - alert_settings: The AlertSettings object
    # - tolerance_crossed: True if tolerance was crossed