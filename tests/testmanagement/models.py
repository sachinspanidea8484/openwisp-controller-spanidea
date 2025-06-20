from django.db import models
from django.utils.html import format_html
from django.contrib import admin

# Create your models here.
class TestSuiteCase(models.Model):
    name = models.CharField(default="",max_length=200)
    description = models.CharField(default="",max_length=200)
    
    # @admin.display
    # def all_testsuites(self):

    #     testsuites = TestSuite.objects.filter(testsuitecase=self)
    #     #testsuite_serializer = TestSuiteSerializer(testsuites, many=True, context={'request': request})
    #     return testsuites
        
    def __str__(self):
        return self.name

class TestSuite(models.Model):
    name = models.CharField(default="",max_length=200)
    description = models.CharField(default="",max_length=200)
    testsuitecase = models.ForeignKey(TestSuiteCase, on_delete=models.CASCADE)
    
    def __str__(self):
        return self.name

class TestCase(models.Model):
    testcase_id = models.AutoField(primary_key=True)
    name = models.CharField(default="",max_length=200)
    description = models.CharField(default="",max_length=200)
    input = models.TextField()
    enabled = models.BooleanField(default=True)
    #testsuite = models.ManyToManyField(TestSuite)
    testsuite = models.ForeignKey(TestSuite, related_name='testcases', on_delete=models.CASCADE)
    def __str__(self):
        return f"{self.testsuite.name} → {self.name}"

    
class TestCategory(models.Model):
    name = models.CharField(default="",max_length=200)
    description = models.CharField(default="",max_length=200)

