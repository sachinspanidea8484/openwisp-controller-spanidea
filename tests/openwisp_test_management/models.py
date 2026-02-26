from swapper import swappable_setting
import reversion
from reversion import revisions as reversion
from .base.models import (
    AbstractTestCategory,
    AbstractTestCase,
    AbstractTestSuite,
    AbstractTestSuiteCase,
    AbstractTestSuiteExecution,
    AbstractTestSuiteExecutionDevice,
    AbstractTestCaseExecution,
    AbstractTestDeviceGroup,
    AbstractTestDeviceGroupDevice,
    AbstractScheduledExecution,
    AbstractExecutionArtifact,
    AbstractExecutionEmailLog

)
from django.utils.translation import gettext_lazy as _

class TestCategory(AbstractTestCategory):
    """
    Concrete model for Test Categories
    """
    class Meta(AbstractTestCategory.Meta):
        abstract = False
        swappable = swappable_setting("test_management", "TestCategory")


class TestCase(AbstractTestCase):
    """
    Concrete model for Test Cases
    """
    class Meta(AbstractTestCase.Meta):
        abstract = False
        swappable = swappable_setting("test_management", "TestCase")

@reversion.register(follow=["suite_cases"])
class TestSuite(AbstractTestSuite):
    """
    Concrete model for Test Suites
    """
    class Meta(AbstractTestSuite.Meta):
        abstract = False
        swappable = swappable_setting("test_management", "TestSuite")

@reversion.register()
class TestSuiteCase(AbstractTestSuiteCase):
    """
    Concrete model for Test Suite Cases
    """
    class Meta(AbstractTestSuiteCase.Meta):
        abstract = False
        swappable = swappable_setting("test_management", "TestSuiteCase")
        default_permissions = ()  #  Add this line to prevent permission creation



@reversion.register(follow=["devices"])
class TestSuiteExecution(AbstractTestSuiteExecution):
    """
    Concrete model for Test Suite Executions
    """
    class Meta(AbstractTestSuiteExecution.Meta):
        abstract = False
        swappable = swappable_setting("test_management", "TestSuiteExecution")
        verbose_name = _("Test Execution")
        verbose_name_plural = _("Test Executions")

class ScheduledExecution(AbstractScheduledExecution):
    class Meta(AbstractScheduledExecution.Meta):
        abstract= False
        swappable= swappable_setting("test_management", "ScheduledExecution")

@reversion.register()
class TestSuiteExecutionDevice(AbstractTestSuiteExecutionDevice):
    """
    Concrete model for Test Suite Execution Devices
    """
    class Meta(AbstractTestSuiteExecutionDevice.Meta):
        abstract = False
        swappable = swappable_setting("test_management", "TestSuiteExecutionDevice")
        default_permissions = ()  


class TestCaseExecution(AbstractTestCaseExecution):
    """
    Concrete model for Test Case Executions
    """
    class Meta(AbstractTestCaseExecution.Meta):
        abstract = False
        swappable = swappable_setting("test_management", "TestCaseExecution")
        default_permissions = () 



@reversion.register(follow=["devices"])
class TestDeviceGroup(AbstractTestDeviceGroup):
    """
    Concrete model for Test Device Groups
    """
    class Meta(AbstractTestDeviceGroup.Meta):
        abstract = False
        swappable = swappable_setting("test_management", "TestDeviceGroup")

@reversion.register()
class TestDeviceGroupDevice(AbstractTestDeviceGroupDevice):
    """
    Concrete model for Test Device Group Devices
    """
    class Meta(AbstractTestDeviceGroupDevice.Meta):
        abstract = False
        swappable = swappable_setting("test_management", "TestDeviceGroupDevice")
        default_permissions = ()  

class ExecutionArtifact(AbstractExecutionArtifact):

    class Meta(AbstractExecutionArtifact.Meta):
        abstract= False
        swappable= swappable_setting("test_management", "ExecutionArtifact")

class ExecutionEmailLog(AbstractExecutionEmailLog):

    class Meta(AbstractExecutionEmailLog.Meta):
        abstract= False
        swappable= swappable_setting("test_management", "ExecutionEmailLog")
