import logging
from copy import deepcopy
from datetime import datetime, timedelta

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from pytz import UTC
from swapper import load_model

from .. import settings as monitoring_settings
from ..monitoring.configuration import ACCESS_TECHNOLOGIES

Chart = load_model('monitoring', 'Chart')
Metric = load_model('monitoring', 'Metric')
AlertSettings = load_model('monitoring', 'AlertSettings')
Device = load_model('config', 'Device')

logger = logging.getLogger(__name__)


class DeviceDataWriter(object):
    """This class is in charge of writing the device metric data.

    Before these methods were shipped in the REST API view but later have
    been moved here to allow writing this data in the background processes
    of OpenWISP.
    """

    def __init__(self, device_data):
        self.device_data = device_data

    def _init_previous_data(self):
        """makes NetJSON interfaces of previous snapshots more easy to access"""
        data = self.device_data.data or {}
        if data:
            data = deepcopy(data)
            data['interfaces_dict'] = {}
        for interface in data.get('interfaces', []):
            data['interfaces_dict'][interface['name']] = interface
        self._previous_data = data

    def _append_metric_data(
        self, metric, value, current=False, time=None, extra_values=None
    ):
        """Appends data for writing.

        Appends to the data structure which holds metric data and which
        will be sent to the timeseries DB.
        """
        self.write_device_metrics.append(
            (
                metric,
                {
                    'value': value,
                    'current': current,
                    'time': time,
                    'extra_values': extra_values,
                },
            )
        )

    def write(self, data, time=None, current=False):
        time = datetime.strptime(time, '%d-%m-%Y_%H:%M:%S.%f').replace(tzinfo=UTC)
        self._init_previous_data()
        self.device_data.data = data
        # saves raw device data
        self.device_data.save_data()
        data = self.device_data.data
        ct = ContentType.objects.get_for_model(Device)
        device_extra_tags = self._get_extra_tags(self.device_data)
        self.write_device_metrics = []
        for interface in data.get('interfaces', []):
            ifname = interface['name']
            if 'mobile' in interface:
                self._write_mobile_signal(
                    interface, ifname, ct, self.device_data.pk, current, time=time
                )
            ifstats = interface.get('statistics', {})
            # Explicitly stated None to avoid skipping in case the stats are zero
            if (
                ifstats.get('rx_bytes') is not None
                or ifstats.get('tx_bytes') is not None
            ):
                field_value = self._calculate_increment(
                    ifname, 'rx_bytes', ifstats.get('rx_bytes', 0)
                )
                extra_values = {
                    'tx_bytes': self._calculate_increment(
                        ifname, 'tx_bytes', ifstats.get('tx_bytes', 0)
                    )
                }
                name = f'{ifname} traffic'
                metric, created = Metric._get_or_create(
                    object_id=self.device_data.pk,
                    content_type_id=ct.id,
                    configuration='traffic',
                    name=name,
                    key='traffic',
                    main_tags={'ifname': Metric._makekey(ifname)},
                    extra_tags=device_extra_tags,
                )
                self._append_metric_data(
                    metric, field_value, current, time=time, extra_values=extra_values
                )
                if created:
                    self._create_traffic_chart(metric)
            try:
                clients = interface['wireless']['clients']
            except KeyError:
                continue
            if not isinstance(clients, list):
                continue
            name = '{0} wifi clients'.format(ifname)
            metric, created = Metric._get_or_create(
                object_id=self.device_data.pk,
                content_type_id=ct.id,
                configuration='clients',
                name=name,
                key='wifi_clients',
                main_tags={'ifname': Metric._makekey(ifname)},
                extra_tags=device_extra_tags,
            )
            # avoid tsdb overwrite clients
            client_time = time
            for client in clients:
                if 'mac' not in client:
                    continue
                self._append_metric_data(
                    metric, client['mac'], current, time=client_time
                )
                client_time += timedelta(microseconds=1)
            if created:
                self._create_clients_chart(metric)
        if 'resources' in data:
            if 'load' in data['resources'] and 'cpus' in data['resources']:
                self._write_cpu(
                    data['resources']['load'],
                    data['resources']['cpus'],
                    self.device_data.pk,
                    ct,
                    current,
                    time=time,
                )
            if 'disk' in data['resources']:
                self._write_disk(
                    data['resources']['disk'], self.device_data.pk, ct, time=time
                )
            if 'memory' in data['resources']:
                self._write_memory(
                    data['resources']['memory'],
                    self.device_data.pk,
                    ct,
                    current,
                    time=time,
                )
                    # ===== ADD CONNECTIONS PROCESSING =====
            if 'connections' in data['resources']:
                logger.info("=" * 50)
                logger.info("🌐 PROCESSING CONNECTIONS DATA")
                logger.info(f"   Connections: {data['resources']['connections']}")
                self._write_connections(
                        data['resources']['connections'],
                        self.device_data.pk,
                        ct,
                        current,
                        time=time,
                )
                logger.info("✅ Connections data processed successfully")
            else:
                logger.info("ℹ️  No connections data in this batch")    

  
          
        try:
            Metric.batch_write(self.write_device_metrics)
        except ValueError as error:
            logger.error(
                f'Failed to write metrics for "{self.device_data.pk}" device.'
                f' Error: {error}'
            )

    def _get_extra_tags(self, device):
        tags = {'organization_id': str(device.organization_id)}
        try:
            device_location = device.devicelocation
        except ObjectDoesNotExist:
            pass
        else:
            tags['location_id'] = str(device_location.location_id)
            if device_location.floorplan_id:
                tags['floorplan_id'] = str(device_location.floorplan_id)
        return Metric._sort_dict(tags)

    def _get_mobile_signal_type(self, signal):
        if not signal:
            return
        access_techs = list(ACCESS_TECHNOLOGIES.keys())
        access_techs.reverse()
        # if only one access technology is in use, return that
        sections = list(signal.keys())
        if len(sections) == 1:
            return sections[0] if sections[0] in access_techs else None
        # if multiple mobile access technologies are in use,
        # return the most evolved technology in use
        for tech in access_techs:
            if tech in signal:
                return tech

    def _write_mobile_signal(self, interface, ifname, ct, pk, current=False, time=None):
        access_type = self._get_mobile_signal_type(interface['mobile'].get('signal'))
        if not access_type:
            return
        data = interface['mobile']['signal'][access_type]
        signal_power = signal_strength = None
        extra_values = {}
        if 'rssi' in data:
            signal_strength = data['rssi']
        if 'rsrp' in data:
            signal_power = data['rsrp']
        elif 'rscp' in data:
            signal_power = data['rscp']
        if signal_power is not None:
            extra_values = {'signal_power': float(signal_power)}
        if signal_strength is not None:
            signal_strength = float(signal_strength)
        if signal_strength is not None or signal_power is not None:
            metric, created = Metric._get_or_create(
                object_id=self.device_data.pk,
                content_type_id=ct.id,
                configuration='signal_strength',
                name='signal strength',
                key='signal',
                main_tags={'ifname': Metric._makekey(ifname)},
            )
            self._append_metric_data(
                metric, signal_strength, current, time=time, extra_values=extra_values
            )
            if created:
                self._create_signal_strength_chart(metric)

        snr = signal_quality = None
        extra_values = {}
        if 'snr' in data:
            snr = data['snr']
        if 'rsrq' in data:
            signal_quality = data['rsrq']
        if 'ecio' in data:
            snr = data['ecio']
        if 'sinr' in data:
            snr = data['sinr']
        if snr is not None:
            extra_values = {'snr': float(snr)}
        if signal_quality is not None:
            signal_quality = float(signal_quality)
        if snr is not None or signal_quality is not None:
            metric, created = Metric._get_or_create(
                object_id=self.device_data.pk,
                content_type_id=ct.id,
                configuration='signal_quality',
                name='signal quality',
                key='signal',
                main_tags={'ifname': Metric._makekey(ifname)},
            )
            self._append_metric_data(
                metric, signal_quality, current, time=time, extra_values=extra_values
            )
            if created:
                self._create_signal_quality_chart(metric)
        # create access technology chart
        metric, created = Metric._get_or_create(
            object_id=self.device_data.pk,
            content_type_id=ct.id,
            configuration='access_tech',
            name='access technology',
            key='signal',
            main_tags={'ifname': Metric._makekey(ifname)},
        )
        self._append_metric_data(
            metric,
            list(ACCESS_TECHNOLOGIES.keys()).index(access_type),
            current,
            time=time,
        )
        if created:
            self._create_access_tech_chart(metric)

    def _write_cpu(
        self, load, cpus, primary_key, content_type, current=False, time=None
    ):
        extra_values = {
            'load_1': float(load[0]),
            'load_5': float(load[1]),
            'load_15': float(load[2]),
        }
        metric, created = Metric._get_or_create(
            object_id=primary_key, content_type_id=content_type.id, configuration='cpu'
        )
        if created:
            self._create_resources_chart(metric, resource='cpu')
            self._create_resources_alert_settings(metric, resource='cpu')
        self._append_metric_data(
            metric,
            100 * float(load[0] / cpus),
            current,
            time=time,
            extra_values=extra_values,
        )

    def _write_disk(
        self, disk_list, primary_key, content_type, current=False, time=None
    ):
        used_bytes, size_bytes, available_bytes = 0, 0, 0
        for disk in disk_list:
            used_bytes += disk['used_bytes']
            size_bytes += disk['size_bytes']
            available_bytes += disk['available_bytes']
        metric, created = Metric._get_or_create(
            object_id=primary_key, content_type_id=content_type.id, configuration='disk'
        )
        if created:
            self._create_resources_chart(metric, resource='disk')
            self._create_resources_alert_settings(metric, resource='disk')
        self._append_metric_data(
            metric, 100 * used_bytes / size_bytes, current, time=time
        )

    def _write_memory(
        self, memory, primary_key, content_type, current=False, time=None
    ):
        extra_values = {
            'total_memory': memory['total'],
            'free_memory': memory['free'],
            'buffered_memory': memory['buffered'],
            'shared_memory': memory['shared'],
        }
        if 'cached' in memory:
            extra_values['cached_memory'] = memory.get('cached')
        percent_used = 100 * (
            1 - (memory['free'] + memory['buffered']) / memory['total']
        )
        # Available Memory is not shown in some systems (older openwrt versions)
        if 'available' in memory:
            extra_values.update({'available_memory': memory['available']})
            if memory['available'] > memory['free']:
                percent_used = 100 * (
                    1 - (memory['available'] + memory['buffered']) / memory['total']
                )
        metric, created = Metric._get_or_create(
            object_id=primary_key,
            content_type_id=content_type.id,
            configuration='memory',
        )
        if created:
            self._create_resources_chart(metric, resource='memory')
            self._create_resources_alert_settings(metric, resource='memory')
        self._append_metric_data(
            metric, percent_used, current, time=time, extra_values=extra_values
        )

    def _calculate_increment(self, ifname, stat, value):
        """Returns how much a counter has incremented since its last saved value."""
        # get previous counters
        data = self._previous_data
        try:
            previous_counter = data['interfaces_dict'][ifname]['statistics'][stat]
        except KeyError:
            # if no previous measurements present, counter will start from zero
            previous_counter = 0
        # if current value is higher than previous value,
        # it means the interface traffic counter is increasing
        # and to calculate the traffic performed since the last
        # measurement we have to calculate the difference
        if value >= previous_counter:
            return int(value - previous_counter)
        # on the other side, if the current value is less than
        # the previous value, it means that the counter was restarted
        # (eg: reboot, configuration reload), so we keep the whole amount
        else:
            return int(value)

    def _create_traffic_chart(self, metric):
        """Creates "traffic (GB)" chart."""
        if 'traffic' not in monitoring_settings.AUTO_CHARTS:
            return
        chart = Chart(metric=metric, configuration='traffic')
        chart.full_clean()
        chart.save()

    def _create_clients_chart(self, metric):
        """Creates "WiFi associations" chart."""
        if 'wifi_clients' not in monitoring_settings.AUTO_CHARTS:
            return
        chart = Chart(metric=metric, configuration='wifi_clients')
        chart.full_clean()
        chart.save()

    def _create_resources_chart(self, metric, resource):
        logger.info(f"Created {resource} metric")
        if resource not in monitoring_settings.AUTO_CHARTS:
            return
        chart = Chart(metric=metric, configuration=resource)
        chart.full_clean()
        chart.save()

    def _create_resources_alert_settings(self, metric, resource):
        alert_settings = AlertSettings(metric=metric)
        alert_settings.full_clean()
        alert_settings.save()

    def _create_signal_strength_chart(self, metric):
        chart = Chart(metric=metric, configuration='signal_strength')
        chart.full_clean()
        chart.save()

    def _create_signal_quality_chart(self, metric):
        chart = Chart(metric=metric, configuration='signal_quality')
        chart.full_clean()
        chart.save()

    def _create_access_tech_chart(self, metric):
        chart = Chart(metric=metric, configuration='access_tech')
        chart.full_clean()
        chart.save()

    
    def _write_connections(
    self, connections, primary_key, content_type, current=False, time=None
):
      """
      Writes network connections metrics to InfluxDB.
      
      Args:
            connections: dict with ipv4 and ipv6 connection counts
                              Example: {
                                    'ipv4': {'tcp': 15, 'udp': 8},
                                    'ipv6': {'tcp': 3, 'udp': 2}
                              }
            primary_key: device UUID
            content_type: ContentType for Device model
            current: bool - is this current/latest data
            time: datetime - timestamp of data
      """
      logger.info("📊 _write_connections() called")
      
      ipv4 = connections.get('ipv4', {})
      ipv6 = connections.get('ipv6', {})
      
      tcp_ipv4 = ipv4.get('tcp', 0)
      udp_ipv4 = ipv4.get('udp', 0)
      tcp_ipv6 = ipv6.get('tcp', 0)
      udp_ipv6 = ipv6.get('udp', 0)
      
      # Calculate total connections
      total_connections = tcp_ipv4 + udp_ipv4 + tcp_ipv6 + udp_ipv6
      
      logger.info(f"   IPv4 - TCP: {tcp_ipv4}, UDP: {udp_ipv4}")
      logger.info(f"   IPv6 - TCP: {tcp_ipv6}, UDP: {udp_ipv6}")
      logger.info(f"   Total: {total_connections}")
      
      if total_connections == 0:
            logger.warning("⚠️  No connections found, skipping write")
            return
      
      # Prepare extra values for additional fields
      extra_values = {
            'tcp_ipv4': int(tcp_ipv4),
            'udp_ipv4': int(udp_ipv4),
            'tcp_ipv6': int(tcp_ipv6),
            'udp_ipv6': int(udp_ipv6),
      }
      
      # Get or create metric in PostgreSQL
      metric, created = Metric._get_or_create(
            object_id=primary_key,
            content_type_id=content_type.id,
            configuration='connections',
      )
      
      logger.info(f"   Metric object - Created: {created}, ID: {metric.pk}, Key: {metric.key}")
      
      # Append data for batch write to InfluxDB
      self._append_metric_data(
            metric,
            int(total_connections),  # main field value
            current,
            time=time,
            extra_values=extra_values,
      )
      
      # Create chart and alert settings for new metrics
      if created:
            logger.info("🆕 First time metric - creating chart and alert settings")
            self._create_resources_chart(metric, resource='connections')
            self._create_resources_alert_settings(metric, resource='connections')
            logger.info("✅ Chart and alert settings created")
      
      logger.info("✅ _write_connections() completed successfully")

