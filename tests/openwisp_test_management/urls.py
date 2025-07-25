from django.urls import include, path
from . import settings as app_settings
from . import views

urlpatterns = [
    # Add the category test cases endpoint
    path('api/category/<uuid:category_id>/test-cases/', 
         views.get_category_test_cases, 
         name='category_test_cases'),
    
    # Test endpoint
    path('api/test/', views.test_api, name='test_api'),
    path('api/categories/', views.list_categories, name='list_categories'),
]

if app_settings.TEST_MANAGEMENT_API_ENABLED:
    urlpatterns += [
        path("api/v1/", include("openwisp_test_management.api.urls")),
    ]