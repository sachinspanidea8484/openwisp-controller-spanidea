from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from openwisp_utils.api.serializers import ValidatedModelSerializer


from openwisp_controller.connection.models import DeviceConnection
from openwisp_controller.config.models import Device

from ..base.models import TestExecutionStatus  # ADD THIS IMPORT

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



# Add this new serializer class
class ExecutionDetailsRequestSerializer(serializers.Serializer):
    """Serializer for execution details request"""
    execution_id = serializers.UUIDField(
        required=True,
        help_text=_("UUID of the test suite execution")
    )
    
    def validate_execution_id(self, value):
        """Validate that execution exists"""
        if not TestSuiteExecution.objects.filter(id=value).exists():
            raise serializers.ValidationError(
                _("TestSuiteExecution with this ID does not exist")
            )
        return value

class DeviceTestDataRequestSerializer(serializers.Serializer):
    """Serializer for test data creation request"""
    device_id = serializers.UUIDField(
        required=True,
        help_text=_("UUID of the device to create test data for")
    )  

class TestCaseExecutionResultSerializer(serializers.Serializer):
    """Serializer for updating test case execution results"""
    execution_id = serializers.UUIDField(
        required=True,
        help_text=_("UUID of the test case execution")
    )
    test_suite_execution_id = serializers.UUIDField(
        required=True,
        help_text=_("UUID of the test suite execution")
    )
    device_id = serializers.UUIDField(
        required=True,
        help_text=_("UUID of the device")
    )
    test_case_id = serializers.UUIDField(
        required=True,
        help_text=_("UUID of the test case")
    )
    status = serializers.ChoiceField(
        choices=TestExecutionStatus.choices,
        required=True,
        help_text=_("Execution status")
    )
    exit_code = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text=_("Exit code from test execution")
    )
    stdout = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        help_text=_("Standard output from test execution")
    )
    stderr = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        help_text=_("Standard error output from test execution")
    )
    
    def validate(self, data):
        """Cross-field validation"""
        # Load the model
        from ..swapper import load_model
        TestCaseExecution = load_model("TestCaseExecution")
        
        # Check if execution exists
        try:
            execution = TestCaseExecution.objects.get(
                id=data['execution_id'],
                test_suite_execution_id=data['test_suite_execution_id'],
                device_id=data['device_id'],
                test_case_id=data['test_case_id']
            )
            data['execution_instance'] = execution
        except TestCaseExecution.DoesNotExist:
            raise serializers.ValidationError({
                "execution_id": _(
                    "TestCaseExecution not found with the provided combination of "
                    "execution_id, test_suite_execution_id, device_id, and test_case_id"
                )
            })
        
        # Validate status transitions
        current_status = execution.status
        new_status = data['status']
        
        # Define valid status transitions
        valid_transitions = {
            TestExecutionStatus.PENDING: [
                TestExecutionStatus.RUNNING,
                TestExecutionStatus.CANCELLED
            ],
            TestExecutionStatus.RUNNING: [
                TestExecutionStatus.SUCCESS,
                TestExecutionStatus.FAILED,
                TestExecutionStatus.TIMEOUT,
                TestExecutionStatus.CANCELLED
            ],
            TestExecutionStatus.SUCCESS: [],  # Terminal state
            TestExecutionStatus.FAILED: [],   # Terminal state
            TestExecutionStatus.TIMEOUT: [],  # Terminal state
            TestExecutionStatus.CANCELLED: []  # Terminal state
        }
        
        # if current_status in valid_transitions:
        #     if new_status not in valid_transitions[current_status] and new_status != current_status:
        #         raise serializers.ValidationError({
        #             "status": _(
        #                 f"Invalid status transition from '{current_status}' to '{new_status}'. "
        #                 f"Valid transitions: {', '.join(valid_transitions[current_status])}"
        #             )
        #         })
        
        return data
    



# serializers.py
class TestSuiteExecutionDeleteSerializer(serializers.Serializer):
    """Serializer for test suite execution deletion confirmation"""
    confirm = serializers.BooleanField(
        required=False,
        default=False,
        help_text=_("Confirm deletion of test suite execution and all related data")
    )
    
    def validate_confirm(self, value):
        """Ensure deletion is confirmed"""
        # if not value:
        #     raise serializers.ValidationError(
        #         _("Please confirm deletion by setting 'confirm' to true")
        #     )
        return value


# serializers.py
class TestSuiteExecutionDeleteAllSerializer(serializers.Serializer):
    """Serializer for complete test data deletion"""
    # confirm = serializers.BooleanField(
    #     required=True,
    #     help_text=_("Confirm deletion of ALL related test data including categories, test cases, and test suites")
    # )
    # force_delete = serializers.BooleanField(
    #     required=False,
    #     default=False,
    #     help_text=_("Force delete even if test cases/categories are used elsewhere")
    # )
    
    def validate_confirm(self, value):
        """Ensure deletion is confirmed"""
        # if not value:
        #     raise serializers.ValidationError(
        #         _("You must confirm deletion by setting 'confirm' to true")
        #     )
        return value
    


# serializers.py
class BulkTestDataCreationSerializer(serializers.Serializer):
    """Serializer for bulk test data creation"""
    
    # Category data
    category = serializers.DictField(
        required=True,
        help_text=_("Category data: {name, code, description}")
    )
    
    # Array of test cases
    test_cases = serializers.ListField(
        child=serializers.DictField(),
        required=True,
        min_length=1,
        help_text=_("Array of test cases: [{name, test_case_id, test_type, description, is_active}]")
    )
    
    # Test suite data
    test_suite = serializers.DictField(
        required=True,
        help_text=_("Test suite data: {name, description, is_active}")
    )
    
    # Array of device IDs for execution
    device_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=True,
        min_length=1,
        help_text=_("Array of device UUIDs to execute test suite on")
    )
    
    # Options
    use_existing = serializers.BooleanField(
        default=True,
        help_text=_("Use existing category/test cases if they exist")
    )
    
    def validate_category(self, value):
        """Validate category data"""
        required_fields = ['name']
        for field in required_fields:
            if field not in value:
                raise serializers.ValidationError(f"Category must have '{field}' field")
        
        if not value.get('name', '').strip():
            raise serializers.ValidationError("Category name cannot be empty")
        
        return value
    
    def validate_test_cases(self, value):
        """Validate test cases data"""
        if not value:
            raise serializers.ValidationError("At least one test case is required")
        
        test_case_ids = set()
        for idx, test_case in enumerate(value):
            # Check required fields
            required_fields = ['name', 'test_case_id', 'test_type']
            for field in required_fields:
                if field not in test_case:
                    raise serializers.ValidationError(
                        f"Test case at index {idx} must have '{field}' field"
                    )
            
            # Validate test_case_id uniqueness in request
            tc_id = test_case.get('test_case_id')
            if tc_id in test_case_ids:
                raise serializers.ValidationError(
                    f"Duplicate test_case_id '{tc_id}' in request"
                )
            test_case_ids.add(tc_id)
            
            # Validate test_type
            test_type = test_case.get('test_type')
            if test_type not in [1, 2]:  # Robot Framework=1, Device Agent=2
                raise serializers.ValidationError(
                    f"Test case at index {idx}: test_type must be 1 (Robot Framework) or 2 (Device Agent)"
                )
        
        return value
    
    def validate_test_suite(self, value):
        """Validate test suite data"""
        required_fields = ['name']
        for field in required_fields:
            if field not in value:
                raise serializers.ValidationError(f"Test suite must have '{field}' field")
        
        if not value.get('name', '').strip():
            raise serializers.ValidationError("Test suite name cannot be empty")
        
        return value
    
    def validate_device_ids(self, value):
        """Validate device IDs exist and have working connections"""
        if not value:
            raise serializers.ValidationError("At least one device is required")
        
        # Check if all devices exist
        existing_devices = Device.objects.filter(id__in=value).values_list('id', flat=True)
        missing_devices = set(value) - set(existing_devices)
        
        if missing_devices:
            raise serializers.ValidationError(
                f"Devices not found: {', '.join(str(d) for d in missing_devices)}"
            )
        
        # Check for working connections
        working_devices = DeviceConnection.objects.filter(
            device_id__in=value,
            is_working=True,
            enabled=True
        ).values_list('device_id', flat=True)
        
        devices_without_connection = set(value) - set(working_devices)
        if devices_without_connection:
            raise serializers.ValidationError(
                f"Devices without working SSH connections: {', '.join(str(d) for d in devices_without_connection)}"
            )
        
        return value
