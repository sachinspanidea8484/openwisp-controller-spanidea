from django.contrib import admin
from .models import TestCase, TestSuite, TestSuiteCase
from .serializer import ChildTestSuitesSerializer

class TestCaseInline(admin.StackedInline):
    model = TestCase
    extra = 0
    
class TestSuiteAdmin(admin.ModelAdmin):
    list_display=('name','testsuitecase','testcase_count')
    search_fields=('name',)
    list_filter=('testsuitecase',)
    inlines = [TestCaseInline]
    def testcase_count(self, obj):
        return obj.testcases.count()
    testcase_count.short_description = 'Number of Test Cases:'

class TestSuiteCaseAdmin(admin.ModelAdmin):
    list_display=('name', 'testsuites')
    search_fields=('name',)

    @admin.display(empty_value="No Test Suite Exists")
    def testsuites(self, obj):
        testsuites = TestSuite.objects.filter(testsuitecase=obj)
        testsuite_serializer = ChildTestSuitesSerializer(testsuites, many=True, )
        return testsuite_serializer.data

class TestCaseAdmin(admin.ModelAdmin):
    list_display=('name','testsuite',)
    search_fields=('name',)
    list_filter=('testsuite',)

# Register your models here.
admin.site.register(TestCase, TestCaseAdmin)
admin.site.register(TestSuite, TestSuiteAdmin)
admin.site.register(TestSuiteCase, TestSuiteCaseAdmin)