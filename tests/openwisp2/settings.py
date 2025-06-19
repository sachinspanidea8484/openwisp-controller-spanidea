import os
import sys

# monitoring
from datetime import timedelta

from celery.schedules import crontab
SHELL = 'shell' in sys.argv or 'shell_plus' in sys.argv


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PROJECT_ROOT = os.path.dirname(os.path.dirname(BASE_DIR))


DEBUG = True
TESTING = os.environ.get("TESTING", False) or sys.argv[1:2] == ["test"]
SELENIUM_HEADLESS = True if os.environ.get("SELENIUM_HEADLESS", False) else False
SHELL = "shell" in sys.argv or "shell_plus" in sys.argv
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

ALLOWED_HOSTS = ["*"]



# SQLITE
# DATABASES = {
#     "default": {
#         "ENGINE": "openwisp_utils.db.backends.spatialite",
#         "NAME": os.path.join(BASE_DIR, "openwisp-controller.db"),
#     }
# }


# SPATIALITE_LIBRARY_PATH = "mod_spatialite.so"

DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": "openwisp2",
        "USER": "openwisp2",
        "PASSWORD": "openwisp2",
        "HOST": "127.0.0.1",
        "PORT": "5432",
    }
}

# monitoring
TIMESERIES_DATABASE = {
    'BACKEND': 'openwisp_monitoring.db.backends.influxdb',
    'USER': 'openwisp',
    'PASSWORD': 'openwisp',
    'NAME': 'openwisp2',
    'HOST': os.getenv('INFLUXDB_HOST', 'localhost'),
    'PORT': '8086',
    # UDP writes are disabled by default
    'OPTIONS': {'udp_writes': False, 'udp_port': 8089},
}

if TESTING:
    if os.environ.get('TIMESERIES_UDP', False):
        TIMESERIES_DATABASE['OPTIONS'] = {'udp_writes': True, 'udp_port': 8091}

SECRET_KEY = "fn)t*+$)ugeyip6-#txyy$5wf2ervc0d2n#h)qb)y5@ly$t*@w"

INSTALLED_APPS = [
    "daphne",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",
    # all-auth
    "django.contrib.sites",
    "openwisp_users.accounts",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "django_extensions",
    # openwisp2 modules
    "openwisp_users",
    "openwisp_controller.config",
    "openwisp_controller.pki",
    "openwisp_controller.geo",
    "openwisp_controller.connection",
    "openwisp_controller.subnet_division",
    "openwisp_notifications",
    "openwisp_ipam",

    # use firmware
    "openwisp_firmware_upgrader",
    "private_storage",


    # monitoring
    'openwisp_monitoring.monitoring',
    'openwisp_monitoring.device',
    'openwisp_monitoring.check',
    'nested_admin',

    
    # openwisp2 admin theme
    # (must be loaded here)
    "openwisp_utils.admin_theme",
    "admin_auto_filters",
    # admin
    "django.contrib.admin",
    "django.forms",
    # other dependencies
    "sortedm2m",
    "reversion",
    "leaflet",
    "flat_json_widget",
    # rest framework
    "rest_framework",
    "rest_framework.authtoken",
    "rest_framework_gis",
    "django_filters",
    "drf_yasg",
    # channels
    "channels",
    "import_export",
    # 'debug_toolbar',
]
EXTENDED_APPS = ("django_x509", "django_loci")

AUTH_USER_MODEL = "openwisp_users.User"
SITE_ID = 1

STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
    "openwisp_utils.staticfiles.DependencyFinder",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # 'debug_toolbar.middleware.DebugToolbarMiddleware',
]

INTERNAL_IPS = ['127.0.0.1' , '10.10.10.10']

ROOT_URLCONF = "openwisp2.urls"

# controller
ASGI_APPLICATION = "openwisp2.asgi.application"

# firmware
# ASGI_APPLICATION = "openwisp2.routing.application"

if not TESTING:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [f"{REDIS_URL}/7"]},
        }
    }
else:
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

# monitoring
# avoid slowing down the test suite with mac vendor lookups
if TESTING:
    OPENWISP_MONITORING_MAC_VENDOR_DETECTION = False
    OPENWISP_MONITORING_API_URLCONF = 'openwisp_monitoring.urls'
    OPENWISP_MONITORING_API_BASEURL = 'http://testserver'
    # for testing AUTO_IPERF3
    OPENWISP_MONITORING_AUTO_IPERF3 = True


TIME_ZONE = "Europe/Rome"
LANGUAGE_CODE = "en-gb"
USE_TZ = True
USE_I18N = False
USE_L10N = False
STATIC_URL = "/static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = f"{os.path.dirname(BASE_DIR)}/media/"

CORS_ORIGIN_ALLOW_ALL = True

# firmware
PRIVATE_STORAGE_ROOT = os.path.join(BASE_DIR, "private", "firmware")



# additional statics 
STATIC_ROOT = os.path.join(os.path.dirname(BASE_DIR), 'static_collected')

# Dynamic static files discovery
STATICFILES_DIRS = []

# Define apps and their potential static/template directories
EXTERNAL_APPS = {
    'openwisp_monitoring': {
        'submodules': ['device', 'monitoring', 'check'],
        'base_path': os.path.join(PROJECT_ROOT, 'openwisp_monitoring')
    },
    'openwisp_firmware_upgrader': {
        'submodules': [''],  # Main module only
        'base_path': os.path.join(PROJECT_ROOT, 'openwisp_firmware_upgrader')
    }
}

# Collect static directories
for app_name, app_config in EXTERNAL_APPS.items():
    for submodule in app_config['submodules']:
        if submodule:
            static_path = os.path.join(app_config['base_path'], submodule, 'static')
        else:
            static_path = os.path.join(app_config['base_path'], 'static')
        
        if os.path.exists(static_path):
            STATICFILES_DIRS.append(static_path)
            print(f"Added static dir: {static_path}")

# Template configuration
TEMPLATE_DIRS = [
    os.path.join(PROJECT_ROOT, "templates"),  # Project-level templates
]

# Collect template directories
for app_name, app_config in EXTERNAL_APPS.items():
    for submodule in app_config['submodules']:
        if submodule:
            template_path = os.path.join(app_config['base_path'], submodule, 'templates')
        else:
            template_path = os.path.join(app_config['base_path'], 'templates')
        
        if os.path.exists(template_path):
            TEMPLATE_DIRS.append(template_path)
            print(f"Added template dir: {template_path}")

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": TEMPLATE_DIRS,
        "OPTIONS": {
            "loaders": [
                "django.template.loaders.filesystem.Loader",
                "openwisp_utils.loaders.DependencyLoader",
                "django.template.loaders.app_directories.Loader",
            ],
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "openwisp_utils.admin_theme.context_processor.menu_groups",
                "openwisp_notifications.context_processors.notification_api_settings",
            ],
        },
    }
]




# TEMPLATES = [
#     {
#         "BACKEND": "django.template.backends.django.DjangoTemplates",
#         "DIRS": [
#             os.path.join(os.path.dirname(BASE_DIR), "templates"),
#             # Add the openwisp_monitoring templates directory
#             os.path.join(BASE_DIR, "..", "..", "openwisp_monitoring", "device", "templates"),
#             os.path.join(BASE_DIR, "..", "..", "openwisp_monitoring", "monitoring", "templates"),
#             os.path.join(BASE_DIR, "..", "..", "openwisp_monitoring", "monitoring", "templates"),

#         ],
#         "OPTIONS": {
#             "loaders": [
#                 "django.template.loaders.filesystem.Loader",
#                 "openwisp_utils.loaders.DependencyLoader",
#                 "django.template.loaders.app_directories.Loader",
#             ],
#             "context_processors": [
#                 "django.template.context_processors.debug",
#                 "django.template.context_processors.request",
#                 "django.contrib.auth.context_processors.auth",
#                 "django.contrib.messages.context_processors.messages",
#                 "openwisp_utils.admin_theme.context_processor.menu_groups",
#                 "openwisp_notifications.context_processors.notification_api_settings",
#             ],
#         },
#     }
# ]

FORM_RENDERER = "django.forms.renderers.TemplatesSetting"

EMAIL_PORT = "1025"  # for testing purposes
LOGIN_REDIRECT_URL = "admin:index"
ACCOUNT_LOGOUT_REDIRECT_URL = LOGIN_REDIRECT_URL
OPENWISP_ORGANIZATION_USER_ADMIN = True  # tests will fail without this setting
OPENWISP_ADMIN_DASHBOARD_ENABLED = True
OPENWISP_CONTROLLER_GROUP_PIE_CHART = True
# during development only
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# monitoring
OPENWISP_MONITORING_MANAGEMENT_IP_ONLY = False


if not TESTING:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": f"{REDIS_URL}/6",
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
            },
        }
    }


# firmware
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

if not TESTING:
    CELERY_BROKER_URL = f"{REDIS_URL}/1"
else:
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True
    CELERY_BROKER_URL = "memory://"


# monitoring
# Celery TIME_ZONE should be equal to django TIME_ZONE
# In order to schedule run_iperf3_checks on the correct time intervals
CELERY_TIMEZONE = TIME_ZONE

CELERY_BEAT_SCHEDULE = {
    'run_checks': {
        'task': 'openwisp_monitoring.check.tasks.run_checks',
        # Executes only ping & config check every 5 min
        'schedule': timedelta(minutes=5),
        'args': (
            [  # Checks path
                'openwisp_monitoring.check.classes.Ping',
                'openwisp_monitoring.check.classes.ConfigApplied',
                'openwisp_monitoring.check.classes.WifiClients',
            ],
        ),
        'relative': True,
    },
    'run_iperf3_checks': {
        'task': 'openwisp_monitoring.check.tasks.run_checks',
        # https://docs.celeryq.dev/en/latest/userguide/periodic-tasks.html#crontab-schedules
        # Executes only iperf3 check every 5 mins from 00:00 AM to 6:00 AM (night)
        'schedule': crontab(minute='*/5', hour='0-6'),
        'args': (['openwisp_monitoring.check.classes.Iperf3'],),
        'relative': True,
    },
}

CELERY_EMAIL_BACKEND = EMAIL_BACKEND

# LOGGING = {
#     "version": 1,
#     "filters": {"require_debug_true": {"()": "django.utils.log.RequireDebugTrue"}},
#     "handlers": {
#         "console": {
#             "level": "DEBUG",
#             "filters": ["require_debug_true"],
#             "class": "logging.StreamHandler",
#         }
#     },
# }
# firmware
# LOGGING = {
#     "version": 1,
#     "filters": {"require_debug_true": {"()": "django.utils.log.RequireDebugTrue"}},
#     "handlers": {
#         "console": {
#             "level": "DEBUG",
#             "filters": ["require_debug_true"],
#             "class": "logging.StreamHandler",
#         }
#     },
#     "loggers": {
#         "py.warnings": {"handlers": ["console"]},
#         "celery": {"handlers": ["console"], "level": "DEBUG"},
#         "celery.task": {"handlers": ["console"], "level": "DEBUG"},
#     },
# }

# monitoring
LOGGING = {
    'version': 1,
    'filters': {'require_debug_true': {'()': 'django.utils.log.RequireDebugTrue'}},
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'filters': ['require_debug_true'],
            'class': 'logging.StreamHandler',
        }
    },
    'loggers': {
        '': {
            # this sets root level logger to log debug and higher level
            # logs to console. All other loggers inherit settings from
            # root level logger.
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django': {
            'handlers': ['console'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
        'py.warnings': {'handlers': ['console'], 'propagate': False},
        'celery': {'handlers': ['console'], 'level': 'DEBUG'},
        'celery.task': {'handlers': ['console'], 'level': 'DEBUG'},
    },
}


# firmware
OPENWISP_CUSTOM_OPENWRT_IMAGES = (
    (
        "customimage-squashfs-sysupgrade.bin",
        {"label": "Custom WAP-1200", "boards": ("CWAP1200",)},
    ),
)
# for firmware testing purposes
OPENWISP_FIRMWARE_UPGRADER_OPENWRT_SETTINGS = {
    "reconnect_delay": 150,
    "reconnect_retry_delay": 30,
    "reconnect_max_retries": 10,
    "upgrade_timeout": 80,
}


if not TESTING and SHELL:
    LOGGING.update(
        {
            "loggers": {
                "django.db.backends": {
                    "level": "DEBUG",
                    "handlers": ["console"],
                    "propagate": False,
                },
            }
        }
    )

DJANGO_LOCI_GEOCODE_STRICT_TEST = False
OPENWISP_CONTROLLER_CONTEXT = {"vpnserver1": "vpn.testdomain.com"}
OPENWISP_USERS_AUTH_API = True

TEST_RUNNER = "openwisp_utils.tests.TimeLoggingTestRunner"

# monitoring
LEAFLET_CONFIG = {
    'TILES': [
        [
            'OSM',
            '//{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        ],
        [
            'Satellite',
            '//server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            '&copy; <a href="http://www.esri.com/">Esri</a> and the GIS User Community',
        ],
    ],
    'RESET_VIEW': False,
}



# monitoring
if os.environ.get("SAMPLE_APP", False):
    # Replace Config
    config_index = INSTALLED_APPS.index("openwisp_controller.config")
    INSTALLED_APPS.remove("openwisp_controller.config")
    INSTALLED_APPS.insert(config_index, "openwisp2.sample_config")
    # Replace Pki
    pki_index = INSTALLED_APPS.index("openwisp_controller.pki")
    INSTALLED_APPS.remove("openwisp_controller.pki")
    INSTALLED_APPS.insert(pki_index, "openwisp2.sample_pki")
    # Replace Geo
    geo_index = INSTALLED_APPS.index("openwisp_controller.geo")
    INSTALLED_APPS.remove("openwisp_controller.geo")
    INSTALLED_APPS.insert(geo_index, "openwisp2.sample_geo")
    # Replace Connection
    connection_index = INSTALLED_APPS.index("openwisp_controller.connection")
    INSTALLED_APPS.remove("openwisp_controller.connection")
    INSTALLED_APPS.insert(connection_index, "openwisp2.sample_connection")
    # Replace Openwisp_Users
    users_index = INSTALLED_APPS.index("openwisp_users")
    INSTALLED_APPS.remove("openwisp_users")
    INSTALLED_APPS.insert(users_index, "openwisp2.sample_users")
    # Replace Subnet Division
    subnet_division_index = INSTALLED_APPS.index("openwisp_controller.subnet_division")
    INSTALLED_APPS.remove("openwisp_controller.subnet_division")
    INSTALLED_APPS.insert(subnet_division_index, "openwisp2.sample_subnet_division")
    # Extended apps
    EXTENDED_APPS = (
        "django_x509",
        "django_loci",
        "openwisp_controller.config",
        "openwisp_controller.pki",
        "openwisp_controller.geo",
        "openwisp_controller.connection",
        "openwisp_controller.subnet_division",
        "openwisp_users",
    )
    # Swapper
    AUTH_USER_MODEL = "sample_users.User"
    OPENWISP_USERS_GROUP_MODEL = "sample_users.Group"
    OPENWISP_USERS_ORGANIZATION_MODEL = "sample_users.Organization"
    OPENWISP_USERS_ORGANIZATIONUSER_MODEL = "sample_users.OrganizationUser"
    OPENWISP_USERS_ORGANIZATIONOWNER_MODEL = "sample_users.OrganizationOwner"
    OPENWISP_USERS_ORGANIZATIONINVITATION_MODEL = "sample_users.OrganizationInvitation"
    CONFIG_DEVICE_MODEL = "sample_config.Device"
    CONFIG_DEVICEGROUP_MODEL = "sample_config.DeviceGroup"
    CONFIG_CONFIG_MODEL = "sample_config.Config"
    CONFIG_TEMPLATETAG_MODEL = "sample_config.TemplateTag"
    CONFIG_TAGGEDTEMPLATE_MODEL = "sample_config.TaggedTemplate"
    CONFIG_TEMPLATE_MODEL = "sample_config.Template"
    CONFIG_VPN_MODEL = "sample_config.Vpn"
    CONFIG_VPNCLIENT_MODEL = "sample_config.VpnClient"
    CONFIG_ORGANIZATIONCONFIGSETTINGS_MODEL = "sample_config.OrganizationConfigSettings"
    CONFIG_ORGANIZATIONLIMITS_MODEL = "sample_config.OrganizationLimits"
    DJANGO_X509_CA_MODEL = "sample_pki.Ca"
    DJANGO_X509_CERT_MODEL = "sample_pki.Cert"
    GEO_LOCATION_MODEL = "sample_geo.Location"
    GEO_FLOORPLAN_MODEL = "sample_geo.FloorPlan"
    GEO_DEVICELOCATION_MODEL = "sample_geo.DeviceLocation"
    CONNECTION_CREDENTIALS_MODEL = "sample_connection.Credentials"
    CONNECTION_DEVICECONNECTION_MODEL = "sample_connection.DeviceConnection"
    CONNECTION_COMMAND_MODEL = "sample_connection.Command"
    SUBNET_DIVISION_SUBNETDIVISIONRULE_MODEL = (
        "sample_subnet_division.SubnetDivisionRule"
    )
    SUBNET_DIVISION_SUBNETDIVISIONINDEX_MODEL = (
        "sample_subnet_division.SubnetDivisionIndex"
    )
else:
    # not needed, these are the default values, left here only for example purposes
    # DJANGO_X509_CA_MODEL = 'pki.Ca'
    # DJANGO_X509_CERT_MODEL = 'pki.Cert'
    pass

    for app in [
        'openwisp_monitoring.monitoring',
        'openwisp_monitoring.check',
        'openwisp_monitoring.device',
    ]:
        INSTALLED_APPS.remove(app)
        # EXTENDED_APPS.append(app)
    INSTALLED_APPS.append('openwisp2.sample_monitoring')
    INSTALLED_APPS.append('openwisp2.sample_check')
    INSTALLED_APPS.append('openwisp2.sample_device_monitoring')
    CHECK_CHECK_MODEL = 'sample_check.Check'
    MONITORING_CHART_MODEL = 'sample_monitoring.Chart'
    MONITORING_METRIC_MODEL = 'sample_monitoring.Metric'
    MONITORING_ALERTSETTINGS_MODEL = 'sample_monitoring.AlertSettings'
    DEVICE_MONITORING_WIFICLIENT_MODEL = 'sample_device_monitoring.WifiClient'
    DEVICE_MONITORING_WIFISESSION_MODEL = 'sample_device_monitoring.WifiSession'
    DEVICE_MONITORING_DEVICEDATA_MODEL = 'sample_device_monitoring.DeviceData'
    DEVICE_MONITORING_DEVICEMONITORING_MODEL = (
        'sample_device_monitoring.DeviceMonitoring'
    )
    # Celery auto detects tasks only from INSTALLED_APPS
    CELERY_IMPORTS = ('openwisp_monitoring.device.tasks',)




if os.environ.get("SAMPLE_APP", False) and TESTING:
    # Required for openwisp-users tests
    OPENWISP_ORGANIZATION_USER_ADMIN = True
    OPENWISP_ORGANIZATION_OWNER_ADMIN = True
    OPENWISP_USERS_AUTH_API = True

# local settings must be imported before test runner otherwise they'll be ignored
try:
    from .local_settings import *
except ImportError:
    pass
