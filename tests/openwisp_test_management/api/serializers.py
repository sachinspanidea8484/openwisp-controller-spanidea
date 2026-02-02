from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from openwisp_utils.api.serializers import ValidatedModelSerializer
from ..swapper import load_model

from openwisp_controller.connection.models import DeviceConnection
from openwisp_controller.config.models import Device
from ..base.models import TestExecutionStatus  # ADD THIS IMPORT
from ..swapper import load_model

# MODEL 
TestCategory = load_model("TestCategory")
TestCase = load_model("TestCase")
TestSuite = load_model("TestSuite")
TestSuiteCase = load_model("TestSuiteCase")
TestSuiteExecution = load_model("TestSuiteExecution")
TestSuiteExecutionDevice = load_model("TestSuiteExecutionDevice")
TestDeviceGroup= load_model("TestDeviceGroup")
ExecutionArtifact = load_model("ExecutionArtifact")



class BaseMeta:
    """Base meta class for all serializers"""
    read_only_fields = ["created", "modified"]


class BaseSerializer(ValidatedModelSerializer):
    """Base serializer for test management models"""
    pass



# ============================================================================
# TEST CATEGORY SERIALIZERS
# ============================================================================

class TestCategorySerializer(ValidatedModelSerializer):
    """
    Serializer for TestCategory List and Create operations
    """
    
    class Meta(BaseMeta):
        model = TestCategory
        fields = "__all__"

    def validate_name(self, value):
        """Validate category name uniqueness (case-insensitive)"""
        qs = TestCategory.objects.filter(name__iexact=value)
        
        # Exclude current instance during updates
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        
        if qs.exists():
            raise serializers.ValidationError(
                _("A test category with this name already exists")
            )
        
        return value

    def validate_code(self, value):
        """Ensure code is not empty"""
        if not value or value.strip() == "":
            raise serializers.ValidationError(
                _("Category code is required and cannot be empty")
            )
        return value.strip()


class TestCaseMinimalSerializer(serializers.ModelSerializer):
    """
    Minimal serializer for TestCase (used in category detail)
    Shows only essential fields
    """
    class Meta:
        model = TestCase
        fields = (
            "id",
            "name",
            "test_case_id",
            "test_type",
            "is_active",
            "created",
        )
        read_only_fields = fields


class TestCategoryDetailSerializer(ValidatedModelSerializer):
    """
    Detailed serializer for TestCategory Retrieve operations
    Includes related test cases based on user permissions
    """
    test_cases = serializers.SerializerMethodField()
    test_case_count = serializers.SerializerMethodField()
    
    class Meta(BaseMeta):
        model = TestCategory
        fields = "__all__"
    
    def get_test_cases(self, obj):
        """
        Get test cases for this category
        - Superusers see all test cases
        - Regular users see only their own test cases (created_by)
        """
        request = self.context.get('request')
        user = request.user if request else None
        
        # Get base queryset
        test_cases = obj.test_cases.all()
        
        # Filter by user permissions
        if user and not user.is_superuser:
            # Non-superusers see only test cases they created
            test_cases = test_cases.filter(created_by=user)
        
        # Serialize and return
        return TestCaseMinimalSerializer(
            test_cases, 
            many=True, 
            context=self.context
        ).data
    
    def get_test_case_count(self, obj):
        """
        Get count of test cases user can see
        - Superusers see total count
        - Regular users see count of their own test cases
        """
        request = self.context.get('request')
        user = request.user if request else None
        
        # Get base queryset
        test_cases = obj.test_cases.all()
        
        # Filter by user permissions
        if user and not user.is_superuser:
            test_cases = test_cases.filter(created_by=user)
        
        return test_cases.count()








# ============================================================================
# TEST SUITE (TEST GROUP) SERIALIZERS
# ============================================================================

class TestSuiteCaseSerializer(serializers.ModelSerializer):
    """Serializer for TestSuiteCase (join table with order)"""
    test_case_name = serializers.CharField(source='test_case.name', read_only=True)
    test_case_id = serializers.CharField(source='test_case.test_case_id', read_only=True)
    
    class Meta:
        model = TestSuiteCase
        fields = ['id', 'test_case', 'test_case_name', 'test_case_id', 'order', 'created', 'modified']
        read_only_fields = ['id', 'created', 'modified', 'test_case_name', 'test_case_id']


class TestCaseForGroupSerializer(serializers.ModelSerializer):
    """Minimal test case serializer for test group"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = TestCase
        fields = [
            'id',
            'name',
            'test_case_id',
            'category',
            'category_name',
            'test_type',
            'is_active',
            'created_by',
            'created',
        ]
        read_only_fields = fields


class TestSuiteSerializer(ValidatedModelSerializer):
    """Serializer for TestSuite (Test Group) List and Create"""
    test_case_count = serializers.SerializerMethodField()
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    
    # ADD THIS FIELD - accepts list of test case UUIDs
    test_case_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
        help_text=_("List of test case UUIDs to add to the group")
    )
    
    class Meta(BaseMeta):
        model = TestSuite
        fields = [
            'id',
            'name',
            'description',
            'is_active',
            'test_case_count',
            'test_case_ids',  # ADD THIS
            'created_by',
            'created_by_username',
            'created',
            'modified',
        ]
        read_only_fields = ['created', 'modified', 'test_case_count', 'created_by_username']
    
    def get_test_case_count(self, obj):
        """Get count of test cases in this group"""
        return obj.test_cases.count()
    
    def validate_name(self, value):
        """Validate test group name uniqueness (case-insensitive)"""
        qs = TestSuite.objects.filter(name__iexact=value)
        
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        
        if qs.exists():
            raise serializers.ValidationError(
                _("A test group with this name already exists")
            )
        
        return value
    
    # ADD THIS METHOD
    def validate_test_case_ids(self, value):
        """Validate that all test case IDs exist"""
        if not value:
            return value
        
        existing_ids = TestCase.objects.filter(id__in=value).values_list('id', flat=True)
        existing_ids_str = [str(id) for id in existing_ids]
        provided_ids_str = [str(id) for id in value]
        
        missing_ids = set(provided_ids_str) - set(existing_ids_str)
        if missing_ids:
            raise serializers.ValidationError(
                _("Test cases not found: {}").format(', '.join(missing_ids))
            )
        
        return value
    
    def create(self, validated_data):
        """Create test group and add test cases"""
        # Extract test_case_ids before creating
        test_case_ids = validated_data.pop('test_case_ids', None)
        
        # Set created_by from request user
        request = self.context.get('request')
        if request and request.user:
            validated_data['created_by'] = request.user
        
        # Create test suite
        instance = super().create(validated_data)
        
        # Add test cases if provided
        if test_case_ids:
            instance.test_cases.set(test_case_ids)
        
        return instance
    
    # ADD THIS METHOD
    def update(self, instance, validated_data):
        """Update test group and test cases"""
        # Extract test_case_ids before updating
        test_case_ids = validated_data.pop('test_case_ids', None)
        
        # Update basic fields
        instance = super().update(instance, validated_data)
        
        # Update test cases if provided
        if test_case_ids is not None:
            instance.test_cases.set(test_case_ids)
        
        return instance
    

class TestSuiteDetailSerializer(ValidatedModelSerializer):
    """Detailed serializer for TestSuite retrieve with test cases"""
    test_cases_detail = serializers.SerializerMethodField()
    test_case_count = serializers.SerializerMethodField()
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    
    # ADD THIS FIELD - accepts list of test case UUIDs
    test_case_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
        help_text=_("List of test case UUIDs to replace all test cases in the group")
    )
    
    class Meta(BaseMeta):
        model = TestSuite
        fields = [
            'id',
            'name',
            'description',
            'is_active',
            'test_case_count',
            'test_cases_detail',
            'test_case_ids',  # ADD THIS
            'created_by',
            'created_by_username',
            'created',
            'modified',
        ]
        read_only_fields = [
            'created',
            'modified',
            'test_case_count',
            'test_cases_detail',
            'created_by',
            'created_by_username'
        ]
    
    def get_test_cases_detail(self, obj):
        """Get ordered test cases with details"""
        suite_cases = obj.suite_cases.all().select_related('test_case', 'test_case__category')
        
        result = []
        for suite_case in suite_cases:
            result.append({
                'id': suite_case.test_case.id,
                'name': suite_case.test_case.name,
                'test_case_id': suite_case.test_case.test_case_id,
                'category': suite_case.test_case.category.id,
                'category_name': suite_case.test_case.category.name,
                'test_type': suite_case.test_case.test_type,
                'is_active': suite_case.test_case.is_active,
                'order': suite_case.order,
                'created_by': suite_case.test_case.created_by_id,
            })
        
        return result
    
    def get_test_case_count(self, obj):
        """Get count of test cases"""
        return obj.test_cases.count()
    
    def validate_name(self, value):
        """Validate test group name uniqueness"""
        qs = TestSuite.objects.filter(name__iexact=value)
        
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        
        if qs.exists():
            raise serializers.ValidationError(
                _("A test group with this name already exists")
            )
        
        return value
    
    # ADD THIS METHOD
    def validate_test_case_ids(self, value):
        """Validate that all test case IDs exist"""
        if not value:
            return value
        
        existing_ids = TestCase.objects.filter(id__in=value).values_list('id', flat=True)
        existing_ids_str = [str(id) for id in existing_ids]
        provided_ids_str = [str(id) for id in value]
        
        missing_ids = set(provided_ids_str) - set(existing_ids_str)
        if missing_ids:
            raise serializers.ValidationError(
                _("Test cases not found: {}").format(', '.join(missing_ids))
            )
        
        return value
    
    def update(self, instance, validated_data):
        """Handle M2M update for test_cases"""
        test_case_ids = validated_data.pop('test_case_ids', None)
        
        # Update basic fields
        instance = super().update(instance, validated_data)
        
        # Update M2M relationship if provided
        if test_case_ids is not None:
            instance.test_cases.set(test_case_ids)
        
        return instance
class AddTestCasesToGroupSerializer(serializers.Serializer):
    """Serializer for adding test cases to a test group"""
    test_case_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        help_text=_("List of test case IDs to add to the group")
    )
    
    def validate_test_case_ids(self, value):
        """Validate test cases exist"""
        existing_ids = TestCase.objects.filter(id__in=value).values_list('id', flat=True)
        existing_ids = [str(id) for id in existing_ids]
        
        missing_ids = set(str(id) for id in value) - set(existing_ids)
        if missing_ids:
            raise serializers.ValidationError(
                _("Test cases not found: {}").format(', '.join(missing_ids))
            )
        
        return value


class RemoveTestCasesFromGroupSerializer(serializers.Serializer):
    """Serializer for removing test cases from a test group"""
    test_case_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        help_text=_("List of test case IDs to remove from the group")
    )


# ============================================================================
# TEST CASE LISTING WITH CATEGORY FILTER SERIALIZER
# ============================================================================

class TestCaseListSerializer(serializers.ModelSerializer):
    """Serializer for test case listing with category filter"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_code = serializers.CharField(source='category.code', read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    suite_count = serializers.SerializerMethodField()
    
    class Meta:
        model = TestCase
        fields = [
            'id',
            'name',
            'test_case_id',
            'category',
            'category_name',
            'category_code',
            'description',
            'test_type',
            'is_active',
            'is_configuration_push_required',
            'suite_count',
            'created_by',
            'created_by_username',
            'created',
            'modified',
        ]
        read_only_fields = fields
    
    def get_suite_count(self, obj):
        """Get count of test suites containing this test case"""
        return obj.test_suites.count()

# OLD

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
            "params",  # ADD THIS - NEW FIELD
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


class TestSuiteListSerializer(TestSuiteSerializer):
    """Lightweight serializer for list views"""
    # category_name = serializers.CharField(source="category.name", read_only=True)
    
    class Meta(BaseMeta):
        model = TestSuite
        fields = [
            "id",
            "name",
            # "category",
            # "category_name",
            "is_active",
            "test_case_count",
            "execution_count",
            "created",
            "modified",
        ]
        read_only_fields = BaseMeta.read_only_fields + [
            "test_case_count",
            "execution_count",
            # "category_name",
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
        # read_only_fields = ["started_at", "completed_at"]

from django.contrib.auth import get_user_model

class ExecutionArtifactSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExecutionArtifact
        fields = (
            "id",
            "device",
            "testcase",
            "config_file",
            "is_pushed",
        )
        read_only_fields = fields

class TestSuiteExecutionSerializer(serializers.ModelSerializer):
    """
    Safe serializer for AbstractTestSuiteExecution
    (OpenWISP + swapper compatible)
    """

    # ---------- READ-ONLY FIELDS ----------
    test_suite_id = serializers.IntegerField(
        source="test_suite.id",
        read_only=True
    )

    device_group_id = serializers.IntegerField(
        source="device_group.id",
        read_only=True
    )

    parent_execution_id = serializers.IntegerField(
        source="parent_execution.id",
        read_only=True
    )

    status = serializers.IntegerField(read_only=True)
    status_display = serializers.CharField(read_only=True)
    active_device_count = serializers.IntegerField(read_only=True)
    is_re_execution = serializers.BooleanField(read_only=True)

    artifacts = ExecutionArtifactSerializer(many=True, read_only=True)

    class Meta:
        model = load_model("TestSuiteExecution")
        fields = [
            "id",
            "name",
            "test_selection_type",

            # write targets (handled dynamically)
            "test_suite",
            "individual_test_cases",

            # read-only ids
            "test_suite_id",
            "device_group_id",
            "parent_execution_id",

            "test_case_execution_order",
            "is_executed",

            "device_count",
            "testcase_count",

            "device_selection",
            "device_group",

            "artifacts",

            "execution_status",
            "execution_start_time",

            "created_by",
            "parent_execution",
            "re_execution_index",

            # computed
            "status",
            "status_display",
            "active_device_count",
            "is_re_execution",

            "created",
            "modified",
        ]
        read_only_fields = (
            "device_count",
            "testcase_count",
            "is_executed",
            "execution_status",
            "execution_start_time",
            "created",
            "modified",
        )

    def get_fields(self):
        fields = super().get_fields()

        TestSuite = load_model("TestSuite")
        TestCase = load_model("TestCase")
        TestDeviceGroup = load_model("TestDeviceGroup")
        User = get_user_model()

        fields["test_suite"] = serializers.PrimaryKeyRelatedField(
            queryset=TestSuite.objects.all(),
            required=False,
            allow_null=True
        )

        fields["individual_test_cases"] = serializers.PrimaryKeyRelatedField(
            many=True,
            queryset=TestCase.objects.all(),
            required=False
        )

        fields["device_group"] = serializers.PrimaryKeyRelatedField(
            queryset=TestDeviceGroup.objects.all(),
            required=False,
            allow_null=True
        )

        fields["created_by"] = serializers.PrimaryKeyRelatedField(
            queryset=User.objects.all(),
            required=False,
            allow_null=True
        )

        return fields

    # ---------- VALIDATION ----------
    def validate(self, attrs):
        test_selection_type = attrs.get(
            "test_selection_type",
            getattr(self.instance, "test_selection_type", None)
        )

        test_suite = attrs.get("test_suite")
        individual_cases = attrs.get("individual_test_cases")

        if test_selection_type == 1 and not test_suite:
            raise serializers.ValidationError({
                "test_suite": "Test group is required when test_selection_type is 'Group'."
            })

        if test_selection_type == 0 and not individual_cases:
            raise serializers.ValidationError({
                "individual_test_cases": "At least one test case is required for individual selection."
            })

        return attrs

class TestSuiteExecutionSerializerOld(ValidatedModelSerializer):
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
    # status_summary = serializers.SerializerMethodField()
    
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
            # "status_summary",
            "created",
            "modified",
        ]
        read_only_fields = BaseMeta.read_only_fields + [
            "is_executed",
            "device_count",
            # "status_summary",
        ]
    
    # def get_status_summary(self, obj):
    #     """Return status summary"""
    #     return obj.status_summary
    
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
            raise serializers.ValidationError(_("Test group must be active"))
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
            # "is_executed",
            # "status_summary",
            "created",
        ]
        read_only_fields = BaseMeta.read_only_fields + [
            "is_executed",
            "device_count",
            # "status_summary",
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
        help_text=_("Confirm deletion of test group execution and all related data")
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
            # ADD THIS - Validate params if provided
            params = test_case.get('params')
            if params is not None:
                if not isinstance(params, dict):
                    raise serializers.ValidationError(
                        f"Test case at index {idx}: params must be a JSON object (dictionary)"
                    )
        
        return value
    
    def validate_test_suite(self, value):
        """Validate test suite data"""
        required_fields = ['name']
        for field in required_fields:
            if field not in value:
                raise serializers.ValidationError(f"Test group must have '{field}' field")
        
        if not value.get('name', '').strip():
            raise serializers.ValidationError("Test group name cannot be empty")
        
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






class AllureReportUploadSerializer(serializers.Serializer):
    """Serializer for uploading Allure report file"""
    report_file = serializers.FileField(
        required=True,
        help_text=_("Allure report HTML file")
    )
    
    def validate_report_file(self, value):
        """Validate the uploaded file"""
        # Check file extension
        if not value.name.endswith('.html'):
            raise serializers.ValidationError(
                _("Only HTML files are allowed for Allure reports")
            )
        
        # Check file size (limit to 50MB)
        if value.size > 50 * 1024 * 1024:
            raise serializers.ValidationError(
                _("File size must not exceed 50MB")
            )
        
        return value


class AllureReportResponseSerializer(BaseSerializer):
    """Serializer for Allure report response"""
    device_name = serializers.CharField(source='device.name', read_only=True)
    device_id = serializers.UUIDField(source='device.id', read_only=True)
    test_suite_name = serializers.CharField(
        source='test_suite_execution.test_suite.name', 
        read_only=True
    )
    execution_id = serializers.UUIDField(
        source='test_suite_execution.id', 
        read_only=True
    )
    report_url = serializers.SerializerMethodField()
    
    class Meta(BaseMeta):
        model = TestSuiteExecutionDevice
        fields = [
            'id',
            'device_id',
            'device_name',
            'test_suite_name',
            'execution_id',
            'status',
            'allure_report_path',
            'report_url',
            'created',
            'modified'
        ]
    
    def get_report_url(self, obj):
        """Get full URL for the report"""
        if obj.allure_report_path:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(f'/media/{obj.allure_report_path}')
        return None
    


class RobotTestResultSerializer(serializers.Serializer):
    execution_id = serializers.UUIDField()
    status = serializers.ChoiceField(choices=[
        ('running', 'running'),
        ('success', 'success'),
        ('failed', 'failed'),
        ('timeout', 'timeout'),
        ('cancelled', 'cancelled'),
    ])
    exit_code = serializers.IntegerField(required=False, allow_null=True)
    stdout = serializers.CharField(required=False, allow_blank=True)
    stderr = serializers.CharField(required=False, allow_blank=True)
    started_at = serializers.DateTimeField(required=False, allow_null=True)
    completed_at = serializers.DateTimeField(required=False, allow_null=True)


class RobotTestRunningResultSerializer(serializers.Serializer):
    execution_id = serializers.UUIDField()
    status = serializers.ChoiceField(choices=[
        ('running', 'running'),
        ('success', 'success'),
        ('failed', 'failed'),
        ('timeout', 'timeout'),
        ('cancelled', 'cancelled'),
    ])

class DeviceTestResultSerializer(serializers.Serializer):
    execution_id = serializers.UUIDField()
    status = serializers.ChoiceField(choices=[
        ('running', 'running'),
        ('success', 'success'),
        ('failed', 'failed'),
        ('timeout', 'timeout'),
        ('cancelled', 'cancelled'),
    ])
    exit_code = serializers.IntegerField(required=False, allow_null=True)
    stdout = serializers.CharField(required=False, allow_blank=True)
    stderr = serializers.CharField(required=False, allow_blank=True)
    started_at = serializers.DateTimeField(required=False, allow_null=True)
    completed_at = serializers.DateTimeField(required=False, allow_null=True)


class OrganisationDevicesSerializer(serializers.Serializer):
    organization_id= serializers.UUIDField()


class TestDeviceGroupSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    class Meta:
        model = TestDeviceGroup  # your concrete model, not abstract
        fields = ['id', 'organization', 'name', 'description','organization_name', 'device_count']
        read_only_fields = ['id', 'device_count']