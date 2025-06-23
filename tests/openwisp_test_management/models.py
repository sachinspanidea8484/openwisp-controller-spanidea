from swapper import swappable_setting

from .base.models import AbstractTestCategory, AbstractTestCase


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