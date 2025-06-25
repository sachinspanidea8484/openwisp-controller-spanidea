from swapper import swappable_setting

from .base.models import (
    AbstractTestCategory,
    AbstractTestCase,
    AbstractTestSuite,
    AbstractTestSuiteCase,
)


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


class TestSuite(AbstractTestSuite):
    """
    Concrete model for Test Suites
    """
    class Meta(AbstractTestSuite.Meta):
        abstract = False
        swappable = swappable_setting("test_management", "TestSuite")


class TestSuiteCase(AbstractTestSuiteCase):
    """
    Concrete model for Test Suite Cases
    """
    class Meta(AbstractTestSuiteCase.Meta):
        abstract = False
        swappable = swappable_setting("test_management", "TestSuiteCase")
        default_permissions = ()  # ← Add this line to prevent permission creation
