class TestManagementException(Exception):
    """Base exception for Test Management module"""
    pass


class TestCategoryException(TestManagementException):
    """Exception related to Test Categories"""
    pass