import os

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path, reverse_lazy
from django.views.generic import RedirectView

from openwisp_controller.config.api.urls import get_api_urls as get_config_api_urls
from openwisp_controller.config.utils import get_controller_urls
from openwisp_controller.connection.api.urls import (
    get_api_urls as get_connection_api_urls,
)
from openwisp_controller.geo.utils import get_geo_urls

from .sample_config import views as config_views
from .sample_config.api import views as config_api_views
from .sample_connection.api import views as connection_api_views
from .sample_geo import views as geo_views




from . import views

if os.environ.get("SAMPLE_APP", False):
    # If you are extending the API views or social views,
    # please import them, otherwise pass `None` in place
    # of these values
    from .sample_radius.api import views as api_views
    from .sample_radius.saml import views as saml_views
    from .sample_radius.social import views as social_views

    radius_urls = path(
        "", include((get_urls(api_views, social_views, saml_views), "radius"))
    )
else:
    api_views = None
    social_views = None
    saml_views = None
    radius_urls = path("", include("openwisp_radius.urls"))

redirect_view = RedirectView.as_view(url=reverse_lazy("admin:index"))

urlpatterns = []

if os.environ.get("SAMPLE_APP", False):
    urlpatterns += [
        path(
            "controller/",
            include(
                (get_controller_urls(config_views), "controller"),
                namespace="controller",
            ),
        ),
        path(
            "",
            include(("openwisp_controller.config.urls", "config"), namespace="config"),
        ),
        path(
            "geo/", include((get_geo_urls(geo_views), "geo_api"), namespace="geo_api")
        ),
        path(
            "api/v1/",
            include(
                (get_config_api_urls(config_api_views), "config_api"),
                namespace="config_api",
            ),
        ),
        path(
            "api/v1/",
            include(
                (
                    get_connection_api_urls(connection_api_views),
                    "connection_api",
                ),
                namespace="connection_api",
            ),
        ),
    ]

urlpatterns += [
    path("", redirect_view, name="index"),
    path('testmanagement/', include('testmanagement.urls')),
    path("admin/", admin.site.urls),
    path("", include("openwisp_controller.urls")),
    path("", include("openwisp_firmware_upgrader.urls")),
    path('', include('openwisp_monitoring.urls')),
    path("", include("openwisp_network_topology.urls")),

    path("accounts/", include("openwisp_users.accounts.urls")),
    radius_urls,
    path("api/v1/", include("openwisp_utils.api.urls")),
    path("api/v1/", include(("openwisp_users.api.urls", "users"), namespace="users")),

  path(
        "captive-portal-mock/login/",
        views.captive_portal_login,
        name="captive_portal_login_mock",
    ),
    path(
        "captive-portal-mock/logout/",
        views.captive_portal_logout,
        name="captive_portal_logout_mock",
    ),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns += staticfiles_urlpatterns()
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG and "debug_toolbar" in settings.INSTALLED_APPS:
    import debug_toolbar

    urlpatterns += [path("__debug__/", include(debug_toolbar.urls))]
