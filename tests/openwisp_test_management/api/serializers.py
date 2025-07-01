from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from openwisp_utils.api.serializers import ValidatedModelSerializer


from openwisp_controller.connection.models import DeviceConnection
from openwisp_controller.config.models import Device

from ..base.models import TestTypeChoices  # ADD THIS IMPORT

from ..swapper import load_model

TestCategory = load_model("TestCategory")
TestCase = load_model("TestCase")
TestSuite = load_model("TestSuite")
TestSuiteCase = load_model("TestSuiteCase")
TestSuiteExecution = load_model("TestSuiteExecution")
TestSuiteExecutionDevice = load_model("TestSuiteExecutionDevice")




class BaseMeta:
    read_only_fields = ["created", "modified"]


class BaseSerializer(ValidatedModelSerializer):
    """Base serializer for test management models"""
    pass


class TestCategorySerializer(BaseSerializer):
    """Serializer for TestCategory model"""
    test_case_count = serializers.IntegerField(read_only=True)
    
    class Meta(BaseMeta):
        model = TestCategory
        fields = [
            "id",
            "name",
            "code",
            "description",
            "test_case_count",
            "created",
            "modified",
        ]
        read_only_fields = BaseMeta.read_only_fields + ["test_case_count"]


    def validate_name(self, value):
        """Ensure name is not empty and properly formatted"""
        if not value or not value.strip():
            raise serializers.ValidationError(_("Name cannot be empty"))
        return value.strip()


class TestCategoryListSerializer(TestCategorySerializer):
    """Lightweight serializer for list views"""
    class Meta(BaseMeta):
        model = TestCategory
        fields = [
            "id",
            "name",
            "test_case_count",
            "created",
            "modified",
        ]
        read_only_fields = BaseMeta.read_only_fields + ["test_case_count"]


class TestCategoryRelationSerializer(serializers.ModelSerializer):
    """Serializer for showing category relationship"""
    class Meta:
        model = TestCategory
        fields = ["id", "name", ]
        read_only_fields = fields


class TestCaseSerializer(ValidatedModelSerializer):
    """Serializer for TestCase model"""
    category_detail = TestCategoryRelationSerializer(source="category", read_only=True)
    test_type_display = serializers.CharField(source='get_test_type_display', read_only=True)  # ADD THIS
    
    class Meta(BaseMeta):
        model = TestCase
        fields = [
            "id",
            "name",
            "test_case_id",
            "category",
            "category_detail",
            "test_type",  # ADD THIS
            "test_type_display",  # ADD THIS
            "description",  # ADD THIS (was missing)
            "is_active",
            "created",
            "modified",
        ]
        read_only_fields = BaseMeta.read_only_fields + [
            "test_type_display",  # ADD THIS
        ]



    def validate_test_case_id(self, value):
        """Ensure test_case_id is unique"""
        if not value or not value.strip():
            raise serializers.ValidationError(_("Test Case ID cannot be empty"))
        
        # Check if we're updating
        if self.instance and self.instance.test_case_id == value:
            return value
        
        # Check for duplicates
        if TestCase.objects.filter(test_case_id=value).exists():
            raise serializers.ValidationError(
                _("A test case with this ID already exists")
            )
        
        return value.strip()

    def validate(self, data):
        """Cross-field validation"""
        # Check unique constraint for category + name
        category = data.get("category", self.instance.category if self.instance else None)
        name = data.get("name", self.instance.name if self.instance else None)
        
        if category and name:
            qs = TestCase.objects.filter(category=category, name__iexact=name)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            
            if qs.exists():
                raise serializers.ValidationError({
                    "name": _(
                        f"A test case with this name already exists in category '{category.name}'"
                    )
                })
        
        return data


class TestCaseListSerializer(TestCaseSerializer):
    """Lightweight serializer for list views"""
    category_name = serializers.CharField(source="category.name", read_only=True)
    test_type_display = serializers.CharField(source='get_test_type_display', read_only=True)  # ADD THIS
    
    class Meta(BaseMeta):
        model = TestCase
        fields = [
            "id",
            "name",
            "test_case_id",
            "category",
            "category_name",
            "test_type",  # ADD THIS
            "test_type_display",  # ADD THIS
            "is_active",
            "created",
            "modified",
        ]
        read_only_fields = BaseMeta.read_only_fields + [
            "category_name",
            "test_type_display",  # ADD THIS
        ]


class TestSuiteCaseSerializer(serializers.ModelSerializer):
    """Serializer for TestSuiteCase through model"""
    test_case_detail = TestCaseListSerializer(source="test_case", read_only=True)
    
    class Meta:
        model = TestSuiteCase
        fields = ["id", "test_case", "test_case_detail", "order"]


class TestSuiteSerializer(ValidatedModelSerializer):
    """Serializer for TestSuite model"""
    category_detail = TestCategoryRelationSerializer(source="category", read_only=True)
    test_case_count = serializers.IntegerField(read_only=True)
    execution_count = serializers.IntegerField(read_only=True)
    test_cases = TestSuiteCaseSerializer(
        source="testsuitecase_set",
        many=True,
        read_only=True
    )
    test_case_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
        help_text=_("List of test case IDs to include in the suite")
    )
    filter_test_type = serializers.IntegerField(
        write_only=True,
        required=False,
        help_text=_("Filter test cases by type (1=Robot Framework, 2=Agent)")
    )
    
    class Meta(BaseMeta):
        model = TestSuite
        fields = [
            "id",
            "name",
            "description",
            "is_active",
            "category",
            "category_detail",
            "test_cases",
            "test_case_ids",
            "test_case_count",
            "execution_count",
            "created",
            "modified",
        ]
        read_only_fields = BaseMeta.read_only_fields + [
            "test_case_count",
            "execution_count",
        ]



    def validate_name(self, value):
        """Ensure name is not empty and properly formatted"""
        if not value or not value.strip():
            raise serializers.ValidationError(_("Name cannot be empty"))
        return value.strip()

    def validate_test_case_ids(self, value):
        """Validate test case IDs belong to the same category"""
        if not value:
            return value
        
        # Get category from instance or data
        category = None
        if self.instance:
            category = self.instance.category
        elif 'category' in self.initial_data:
            try:
                category = TestCategory.objects.get(pk=self.initial_data['category'])
            except TestCategory.DoesNotExist:
                raise serializers.ValidationError(_("Invalid category"))
        
        if not category:
            raise serializers.ValidationError(_("Category must be specified"))
        
        # Build test case queryset
        test_cases_qs = TestCase.objects.filter(
            id__in=value,
            category=category,
            is_active=True
        )
        
        # Apply test_type filter if provided
        if 'filter_test_type' in self.initial_data:
            test_cases_qs = test_cases_qs.filter(
                test_type=self.initial_data['filter_test_type']
            )
        
        if test_cases_qs.count() != len(value):
            raise serializers.ValidationError(_("Some test case IDs are invalid or don't match the filter"))
        
        return value

    def create(self, validated_data):
        """Create test suite with test cases"""
        test_case_ids = validated_data.pop('test_case_ids', [])
        instance = super().create(validated_data)
        
        # Add test cases with order
        for order, test_case_id in enumerate(test_case_ids, start=1):
            TestSuiteCase.objects.create(
                test_suite=instance,
                test_case_id=test_case_id,
                order=order
            )
        
        return instance

    def update(self, instance, validated_data):
        """Update test suite with test cases"""
        test_case_ids = validated_data.pop('test_case_ids', None)
        instance = super().update(instance, validated_data)
        
        if test_case_ids is not None:
            # Clear existing test cases
            instance.testsuitecase_set.all().delete()
            
            # Add new test cases with order
            for order, test_case_id in enumerate(test_case_ids, start=1):
                TestSuiteCase.objects.create(
                    test_suite=instance,
                    test_case_id=test_case_id,
                    order=order
                )
        
        return instance


class TestSuiteListSerializer(TestSuiteSerializer):
    """Lightweight serializer for list views"""
    category_name = serializers.CharField(source="category.name", read_only=True)
    
    class Meta(BaseMeta):
        model = TestSuite
        fields = [
            "id",
            "name",
            "category",
            "category_name",
            "is_active",
            "test_case_count",
            "execution_count",
            "created",
            "modified",
        ]
        read_only_fields = BaseMeta.read_only_fields + [
            "test_case_count",
            "execution_count",
            "category_name",
        ]        









class DeviceSerializer(serializers.ModelSerializer):
    """Minimal device serializer for execution"""
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    
    class Meta:
        model = Device
        fields = ["id", "name", "organization_name"]


class TestSuiteExecutionDeviceSerializer(serializers.ModelSerializer):
    """Serializer for execution devices"""
    device_detail = DeviceSerializer(source="device", read_only=True)
    
    class Meta:
        model = TestSuiteExecutionDevice
        fields = [
            "id",
            "device",
            "device_detail",
            "status",
            "started_at",
            "completed_at",
            "output",
        ]
        read_only_fields = ["started_at", "completed_at"]


class TestSuiteExecutionSerializer(ValidatedModelSerializer):
    """Serializer for Test Suite Executions"""
    test_suite_detail = TestSuiteListSerializer(source="test_suite", read_only=True)
    devices = TestSuiteExecutionDeviceSerializer(
        many=True,
        read_only=True
    )
    device_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=True,
        help_text=_("List of device IDs to execute the test suite on")
    )
    device_count = serializers.IntegerField(read_only=True)
    status_summary = serializers.SerializerMethodField()
    
    class Meta(BaseMeta):
        model = TestSuiteExecution
        fields = [
            "id",
            "test_suite",
            "test_suite_detail",
            "devices",
            "device_ids",
            "device_count",
            "is_executed",
            "status_summary",
            "created",
            "modified",
        ]
        read_only_fields = BaseMeta.read_only_fields + [
            "is_executed",
            "device_count",
            "status_summary",
        ]
    
    def get_status_summary(self, obj):
        """Return status summary"""
        return obj.status_summary
    
    def validate_device_ids(self, value):
        """Validate device IDs have working SSH connections"""
        if not value:
            raise serializers.ValidationError(_("At least one device must be selected"))
        
        # Get devices with working connections
        working_device_ids = DeviceConnection.objects.filter(
            is_working=True,
            enabled=True,
            device_id__in=value
        ).values_list('device_id', flat=True)
        
        # Check if all provided devices have working connections
        invalid_devices = set(value) - set(working_device_ids)
        if invalid_devices:
            raise serializers.ValidationError(
                _("Some devices do not have working SSH connections")
            )
        
        return value
    
    def validate_test_suite(self, value):
        """Ensure test suite is active"""
        if not value.is_active:
            raise serializers.ValidationError(_("Test suite must be active"))
        return value
    
    def create(self, validated_data):
        """Create execution with devices"""
        device_ids = validated_data.pop('device_ids')
        
        # Create execution
        execution = super().create(validated_data)
        
        # Create device executions
        for device_id in device_ids:
            TestSuiteExecutionDevice.objects.create(
                test_suite_execution=execution,
                device_id=device_id
            )
        
        return execution


class TestSuiteExecutionListSerializer(TestSuiteExecutionSerializer):
    """Lightweight serializer for list views"""
    test_suite_name = serializers.CharField(source="test_suite.name", read_only=True)
    
    class Meta(BaseMeta):
        model = TestSuiteExecution
        fields = [
            "id",
            "test_suite",
            "test_suite_name",
            "device_count",
            "is_executed",
            "status_summary",
            "created",
        ]
        read_only_fields = BaseMeta.read_only_fields + [
            "is_executed",
            "device_count",
            "status_summary",
            "test_suite_name",
        ]
