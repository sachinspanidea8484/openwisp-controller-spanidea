from swapper import swappable_setting

from .base.models import AbstractTestCategory


class TestCategory(AbstractTestCategory):
    """
    Concrete model for Test Categories
    """
    class Meta(AbstractTestCategory.Meta):
        abstract = False
        swappable = swappable_setting("test_management", "TestCategory")