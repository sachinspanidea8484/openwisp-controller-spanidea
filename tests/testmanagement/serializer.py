from rest_framework import serializers
from .models import TestCase, TestSuite,TestSuiteCase

class TestCaseSerializer(serializers.ModelSerializer):
    testcase_id = serializers.ReadOnlyField()
    class Meta:
        model = TestCase
        fields = '__all__'

class TestSuiteSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField()
    class Meta:
        model = TestSuite
        fields = '__all__'

class TestSuiteCaseSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField()
    class Meta:
        model = TestSuiteCase
        fields = '__all__'

class ChildTestSuitesSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestSuite
        fields = ['name',]