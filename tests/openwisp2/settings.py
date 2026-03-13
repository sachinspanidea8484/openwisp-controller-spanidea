import os
import sys
from datetime import timedelta
from import_export.formats.base_formats import XLSX,CSV
import warnings
from pathlib import Path





from dotenv import load_dotenv
load_dotenv()
from celery.schedules import crontab



warnings.filterwarnings("ignore", message="app_settings.USERNAME_REQUIRED is deprecated")
warnings.filterwarnings("ignore", message="app_settings.EMAIL_REQUIRED is deprecated")


EXECUTOR_SERVER_IP: str = os.getenv('EXECUTOR_SERVER_IP', "http://172.17.0.1:8080")
OPENWISP_SERVER_IP: str = os.getenv('OPENWISP_SERVER_IP', "http://172.17.0.1:8000")
OPENWISP_CONTROLLER_API_HOST: str = os.getenv('OPENWISP_CONTROLLER_API_HOST', "http://172.17.0.1:8000")
SHOW_RE_EXECUTION : bool = True
EXECUTION_HISTORY_AUTO_REFRESH_TIME: int = os.getenv('EXECUTION_HISTORY_AUTO_REFRESH_TIME', 60)
EXECUTION_HISTORY_REFRESH_INTERVAL= os.getenv('EXECUTION_HISTORY_REFRESH_INTERVAL', 60)
OPENWISP_NOTIFICATIONS_EMAIL_ENABLED = False
SHELL = 'shell' in sys.argv or 'shell_plus' in sys.argv
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(BASE_DIR))
ACCOUNT_AUTHENTICATION_METHOD = "username_email" 
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_EMAIL_VERIFICATION = "optional"  
ACCOUNT_LOGIN_METHODS = ["username", "email", "phone"]
IMPORT_EXPORT_FORMATS=[CSV,XLSX]
DJANGO_LOG_LEVEL = os.getenv('DJANGO_LOG_LEVEL', 'INFO')
DEBUG = os.getenv('DEBUG_MODE', True)
TESTING = False
SELENIUM_HEADLESS = True
SHELL = "shell" in sys.argv or "shell_plus" in sys.argv
REDIS_URL = "redis://redis:6379" 
ALLOWED_HOSTS = ["*"]
OPENWISP_RADIUS_FREERADIUS_ALLOWED_HOSTS = ["*"]
OPENWISP_RADIUS_COA_ENABLED = True
OPENWISP_RADIUS_ALLOWED_MOBILE_PREFIXES = ["+44", "+39", "+237", "+595"]
CELERY_BROKER_TRANSPORT_OPTIONS = {
    "visibility_timeout": 3600,  # 1 hour per task
    "socket_keepalive": True,    # keeps TCP alive
    "health_check_interval": 30,
    "retry_on_timeout": True,
}
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BROKER_CONNECTION_MAX_RETRIES = 100
INTERNAL_IPS =  ['127.0.0.1' , '10.10.10.10',
'54.234.248.241' ,'10.8.12.123' ,'192.168.201.37' , '0.0.0.0'
                ]
# Database
DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": os.getenv('DB_NAME', 'openwisp2'),
        "USER": os.getenv('DB_USER', 'openwisp2'),
        "PASSWORD": os.getenv('DB_PASS', 'openwisp2'),
        "HOST": os.getenv('DB_HOST', 'postgres'),
        "PORT": os.getenv('DB_PORT', '5432'),
    }
}
# monitoring
TIMESERIES_DATABASE = {
    'BACKEND': 'openwisp_monitoring.db.backends.influxdb',
    'USER': os.getenv('INFLUXDB_USER', 'openwisp'),
    'PASSWORD': os.getenv('INFLUXDB_PASS', 'openwisp'),
    'NAME': os.getenv('INFLUXDB_NAME', 'openwisp2'),
    'HOST': os.getenv('INFLUXDB_HOST', 'influxdb'),
    'PORT': os.getenv('INFLUXDB_PORT', '8086'),
    'OPTIONS': {'udp_writes': False, 'udp_port': 8089},
}
if TESTING:
    if True:
        TIMESERIES_DATABASE['OPTIONS'] = {'udp_writes': True, 'udp_port': 8091}

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    raise ValueError("DJANGO_SECRET_KEY environment variable is not set")

INSTALLED_APPS = [
    "daphne",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",
    "django.contrib.humanize",
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
    # network topology
    "openwisp_network_topology",
    "openwisp_network_topology.integrations.device",
    # monitoring
    'openwisp_monitoring.monitoring',
    'openwisp_monitoring.device',
    'openwisp_monitoring.check',
    'nested_admin',
    # social login
    "allauth.socialaccount.providers.facebook",
    "allauth.socialaccount.providers.google",
    # openwisp radius
    "openwisp_radius",
    "openwisp2.integrations",
    "djangosaml2",
    # radius
    "dj_rest_auth",
    "dj_rest_auth.registration",
    # openwisp test management
    'openwisp_test_management',
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
    "djangosaml2.middleware.SamlSessionMiddleware",

    "openwisp_test_management.middleware.ProtectedMediaMiddleware",


]
if DEBUG:
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = True
else:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SAML_ALLOWED_HOSTS = []
SAML_USE_NAME_ID_AS_USERNAME = True
SAML_CREATE_UNKNOWN_USER = True
SAML_CONFIG = {}
AUTH_PASSWORD_VALIDATORS = []

# Fix — restore Django defaults for production
if not DEBUG:
    AUTH_PASSWORD_VALIDATORS = [
        {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
        {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
        {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
        {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
    ]
else:
    AUTH_PASSWORD_VALIDATORS = []
ROOT_URLCONF = "openwisp2.urls"
ASGI_APPLICATION = "openwisp2.asgi.application"
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
if TESTING:
    OPENWISP_MONITORING_MAC_VENDOR_DETECTION = False
    OPENWISP_MONITORING_API_URLCONF = 'openwisp_monitoring.urls'
    OPENWISP_MONITORING_API_BASEURL = 'http://testserver'
    # for testing AUTO_IPERF3
    OPENWISP_MONITORING_AUTO_IPERF3 = True
TIME_ZONE = os.getenv('TIME_ZONE', 'Asia/Kolkata')
LANGUAGE_CODE = os.getenv('DJANGO_LANGUAGE_CODE', "en-gb")
USE_TZ = True
USE_I18N = True
USE_L10N = False
STATIC_URL = "/static/"
MEDIA_URL = "/media/"
# Paths
MEDIA_ROOT = os.getenv('MEDIA_ROOT', '/opt/openwisp/media/')
STATIC_ROOT = os.getenv('STATIC_ROOT', '/opt/openwisp/static_collected/')
PRIVATE_STORAGE_ROOT = os.getenv('PRIVATE_STORAGE_ROOT', '/opt/openwisp/private/firmware')
ROOT_PATH= Path(__file__).resolve().parent.parent
TEST_SCRIPT_MEDIA_ROOT= "/opt/openwisp/media/test_case"
TEST_SCRIPT_MEDIA_URL="/media/"
CORS_ORIGIN_ALLOW_ALL = os.getenv('CORS_ORIGIN_ALLOW_ALL', 'True') == 'True'
TEST_SCRIPT_MEDIA_ROOT_ZIP= "/opt/openwisp/media"
MEDIA_ROOT_TEMP= ROOT_PATH /"media/tmp"
AUTO_REFRESH_INTERVAL=60
STATICFILES_DIRS = []
EXTERNAL_APPS = {
    'openwisp_monitoring': {
        'submodules': ['device', 'monitoring', 'check'],
        'base_path': os.path.join(PROJECT_ROOT, 'openwisp_monitoring')
    },
    'openwisp_firmware_upgrader': {
        'submodules': [''],  # Main module only
        'base_path': os.path.join(PROJECT_ROOT, 'openwisp_firmware_upgrader')
    },
    'openwisp_network_topology': {
        'submodules': [''],  # Main module only
        'base_path': os.path.join(PROJECT_ROOT, 'openwisp_network_topology')
    },
        'openwisp_radius': {
        'submodules': [''],  # Main module only
        'base_path': os.path.join(PROJECT_ROOT, 'openwisp_radius')
    },
     'openwisp_test_management': {
        'submodules': [''],  # Main module only
        'base_path': os.path.join(PROJECT_ROOT, 'openwisp_test_management')
    }
}

for app_name, app_config in EXTERNAL_APPS.items():
    for submodule in app_config['submodules']:
        if submodule:
            static_path = os.path.join(app_config['base_path'], submodule, 'static')
        else:
            static_path = os.path.join(app_config['base_path'], 'static')
        
        if os.path.exists(static_path):
            STATICFILES_DIRS.append(static_path)
            # print(f"Added static dir: {static_path}")

TEMPLATE_DIRS = [
    os.path.join(PROJECT_ROOT, "templates"), 
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
            # print(f"Added template dir: {template_path}")

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
                "openwisp_controller.context_processors.controller_api_settings"
            ],
        },
    }
]
FORM_RENDERER = "django.forms.renderers.TemplatesSetting"
LOGIN_REDIRECT_URL = "admin:index"
ACCOUNT_LOGOUT_REDIRECT_URL = LOGIN_REDIRECT_URL
OPENWISP_ORGANIZATION_USER_ADMIN = True  # tests will fail without this setting
OPENWISP_ADMIN_DASHBOARD_ENABLED = True
OPENWISP_CONTROLLER_GROUP_PIE_CHART = True
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
# # monitoring
OPENWISP_MONITORING_MANAGEMENT_IP_ONLY = False
# radius
SOCIALACCOUNT_PROVIDERS = {
    "facebook": {
        "METHOD": "oauth2",
        "SCOPE": ["email", "public_profile"],
        "AUTH_PARAMS": {"auth_type": "reauthenticate"},
        "INIT_PARAMS": {"cookie": True},
        "FIELDS": ["id", "email", "name", "first_name", "last_name", "verified"],
        "VERIFIED_EMAIL": True,
    },
    "google": {"SCOPE": ["profile", "email"], "AUTH_PARAMS": {"access_type": "online"}},
}
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
SESSION_ENGINE = "django.contrib.sessions.backends.db"  # Use database sessions for now
AUTHENTICATION_BACKENDS = [
    'allauth.account.auth_backends.AuthenticationBackend',
    'django.contrib.auth.backends.ModelBackend',
]
CSRF_TRUSTED_ORIGINS = []
SESSION_CACHE_ALIAS = "default"
if not TESTING:
    CELERY_BROKER_URL = f"{REDIS_URL}/1"
    CELERY_RESULT_BACKEND = f"{REDIS_URL}/1"
else:
    OPENWISP_RADIUS_GROUPCHECK_ADMIN = True
    OPENWISP_RADIUS_GROUPREPLY_ADMIN = True
    OPENWISP_RADIUS_USERGROUP_ADMIN = True
    OPENWISP_RADIUS_USER_ADMIN_RADIUSTOKEN_INLINE = True
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True
    CELERY_BROKER_URL = "memory://"


CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60 
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  
CELERY_TASK_ACKS_LATE = True  
CELERY_WORKER_PREFETCH_MULTIPLIER = 1 
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000 
CELERY_TASK_DEFAULT_RETRY_DELAY = 60  
CELERY_TASK_MAX_RETRIES = 3
CELERY_RESULT_EXPIRES = 3600  
# Monitoring
CELERY_SEND_TASK_SENT_EVENT = True
CELERY_SEND_TASK_ERROR_EMAILS = True
CELERY_BEAT_SCHEDULE = {
    'run_checks': {
        'task': 'openwisp_monitoring.check.tasks.run_checks',
        # Executes only ping & config check every 1 min
        'schedule': timedelta(minutes=1),
        # 'schedule': timedelta(seconds=30),

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

    'timeout-stuck-tests': {
        'task': 'openwisp_test_management.tasks.timeout_stuck_tests',
        'schedule': crontab(minute='*/30'),  # Run every 30 minutes
    },
    'check-scheduled-executions-every-minute': {
        'task': 'openwisp_test_management.tasks.check_and_execute_scheduled',
        'schedule': 60,
        'options': {
            'expires': 55,  # Task expires if not executed within 55 seconds(if not even started from queue, no effect on execution)
        }
    },
    # Cleanup old completed executions daily
    'cleanup-old-executions': {
        'task': 'openwisp_test_management.tasks.cleanup_old_executions',
        'schedule': crontab(hour=2, minute=0),  # Run at 2 AM daily
    },


     'retry-failed-emails-hourly': {
        'task': 'openwisp_test_management.tasks.retry_failed_emails',
        'schedule': 3600,  # Every hour
        'kwargs': {'max_age_hours': 24}
    },
    'cleanup-old-email-logs-weekly': {
        'task': 'openwisp_test_management.tasks.cleanup_old_email_logs',
        'schedule': 604800,  # Every week
        'kwargs': {'days_to_keep': 30}
    },
}

CELERY_EMAIL_BACKEND = EMAIL_BACKEND
# SENDSMS_BACKEND = "sendsms.backends.console.SmsBackend"
OPENWISP_RADIUS_EXTRA_NAS_TYPES = (("cisco", "Cisco Router"),)
# Add this to your REST_AUTH configuration
REST_AUTH = {
    "SESSION_LOGIN": False,
    "PASSWORD_RESET_SERIALIZER": "openwisp_radius.api.serializers.PasswordResetSerializer",
    "REGISTER_SERIALIZER": "openwisp_radius.api.serializers.RegisterSerializer",
}
# Add ACCOUNT settings to properly configure allauth
ACCOUNT_SIGNUP_FIELDS = ['email*', 'username*', 'password1*', 'password2*']
ACCOUNT_EMAIL_VERIFICATION = "optional"  # or "mandatory" or "none"
ACCOUNT_EMAIL_CONFIRMATION_ANONYMOUS_REDIRECT_URL = "email_confirmation_success"
ACCOUNT_EMAIL_CONFIRMATION_AUTHENTICATED_REDIRECT_URL = "email_confirmation_success"
SAML_CSP_HANDLER = ''
# network topology 
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "require_debug_false": {"()": "django.utils.log.RequireDebugFalse"},
        "require_debug_true": {"()": "django.utils.log.RequireDebugTrue"},
    },
    "formatters": {
        "simple": {"format": "[%(levelname)s] %(message)s"},
        "verbose": {
            "format": "\n\n[%(levelname)s %(asctime)s] module: %(module)s, process: %(process)d, thread: %(thread)d\n%(message)s"
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "filters": ["require_debug_true"],
            "formatter": "simple",
        },
        "mail_admins": {
            "level": "ERROR",
            "filters": ["require_debug_false"],
            "class": "django.utils.log.AdminEmailHandler",
        },
        "main_log": {
            "level": "ERROR",
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "verbose",
            "filename": os.path.join(BASE_DIR, "error.log"),
            "maxBytes": 5242880.0,
            "backupCount": 3,
        },
    },
    "root": {"level": "INFO", "handlers": ["main_log", "console", "mail_admins"]},
    "loggers": {"py.warnings": {"handlers": ["console"]}},
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
# Test Dir path on Openwrt
OPENWRT_TESTCASE_DIR = "/root/Test_Cases/"

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
    pass
    CELERY_IMPORTS = ('openwisp_monitoring.device.tasks',)




if os.environ.get("SAMPLE_APP", False) and TESTING:
    # Required for openwisp-users tests
    OPENWISP_ORGANIZATION_USER_ADMIN = True
    OPENWISP_ORGANIZATION_OWNER_ADMIN = True
    OPENWISP_USERS_AUTH_API = True

# CORS headers, useful during development and testing
try:
    import corsheaders  # noqa

    INSTALLED_APPS.append("corsheaders")
    MIDDLEWARE.insert(
        MIDDLEWARE.index("django.middleware.common.CommonMiddleware"),
        "corsheaders.middleware.CorsMiddleware",
    )
    # WARNING: for development only!
    CORS_ORIGIN_ALLOW_ALL = True
except ImportError:
    pass
# for test management
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_RATES': {
        'test_management': '1000/minute',
    }
}
# local settings must be imported before test runner otherwise they'll be ignored
try:
    from .local_settings import *
except ImportError:
    pass

FORM_RENDERER = "django.forms.renderers.TemplatesSetting"
