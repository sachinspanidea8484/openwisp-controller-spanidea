from django.http import HttpResponse
from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from rest_framework import status
from rest_framework import viewsets
from .models import TestCase, TestSuite, TestSuiteCase
from .serializer import TestCaseSerializer, TestSuiteSerializer, TestSuiteCaseSerializer

class TestCaseViewSet(viewsets.ModelViewSet):
    queryset = TestCase.objects.all()
    serializer_class = TestCaseSerializer

class TestSuiteViewSet(viewsets.ModelViewSet):
    queryset = TestSuite.objects.all()
    serializer_class = TestSuiteSerializer


    @action(detail=True, methods=['get'])
    def testcases(self, request, pk=None):
        try:
            testsuite = TestSuite.objects.get(pk=pk)
            testcases = TestCase.objects.filter(testsuite=testsuite)
            testcase_serializer = TestCaseSerializer(testcases, many=True, context={'request': request})
            return Response(testcase_serializer.data)
        except Exception as e:
            return Response({'message': "Error!!! TestSuite does not exist."})

class TestSuiteCaseViewSet(viewsets.ModelViewSet):
    queryset = TestSuiteCase.objects.all()
    serializer_class = TestSuiteSerializer


    @action(detail=True, methods=['get'])
    def testsuites(self, request, pk=None):
        try:
            testsuitecase = TestSuiteCase.objects.get(pk=pk)
            testsuites = TestSuite.objects.filter(testsuitecase=testsuitecase)
            testsuite_serializer = TestSuiteSerializer(testsuites, many=True, context={'request': request})
            return Response(testsuite_serializer.data)
        except Exception as e:
            return Response({'message': "Error!!! TestSuiteCase does not exist."})

@api_view(['GET'])
def get_testcase(request):
    testcase = TestCase.objects.all()
    serializedData = TestCaseSerializer(testcase, many=True).data
    return Response(serializedData)

@api_view(['POST'])
def create_testcase(request):
    data = request.data
    serializer = TestCaseSerializer(data=data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

def index(request):
    return HttpResponse("Test Management Module")