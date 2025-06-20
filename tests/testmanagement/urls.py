from django.urls import path, include
from . import views
from rest_framework import routers
#from . import get_testcase

router = routers.DefaultRouter()
router.register(r'testcases', views.TestCaseViewSet)
router.register(r'testsuites', views.TestSuiteViewSet)
router.register(r'testsuitecases', views.TestSuiteCaseViewSet)
urlpatterns = [
    #path('', views.index, name='index'),
    path('', include(router.urls)),
    #path('gettestcase/', views.get_testcase, name='gettestcase'),
    #path('createtestcase/', views.create_testcase, name='gettestcase'),
]