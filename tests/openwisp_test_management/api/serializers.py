from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from openwisp_utils.api.serializers import ValidatedModelSerializer
from ..swapper import load_model
from django.conf import settings
import os
from openwisp_controller.connection.models import DeviceConnection
from openwisp_controller.config.models import Device
from openwisp_users.models import Organization

from django.core.validators import RegexValidator, MinLengthValidator, MaxLengthValidator
from django.utils.translation import gettext_lazy as _

from ..base.models import TestExecutionStatus  # ADD THIS IMPORT
from ..swapper import load_model
from django.core.exceptions import ValidationError
from django.db import models
from uuid import UUID
import json

from openwisp_users.api.mixins import FilterSerializerByOrgManaged

# MODEL 
TestCategory = load_model("TestCategory")
TestCase = load_model("TestCase")
TestSuite = load_model("TestSuite")
TestSuiteCase = load_model("TestSuiteCase")
TestSuiteExecution = load_model("TestSuiteExecution")
TestSuiteExecutionDevice = load_model("TestSuiteExecutionDevice")
TestDeviceGroup= load_model("TestDeviceGroup")
ExecutionArtifact = load_model("ExecutionArtifact")

from .utilities import TestTypeChoices, update_robot_file_tag

class BaseMeta:
    """Base meta class for all serializers"""
    read_only_fields = ["created", "modified"]


class BaseSerializer(ValidatedModelSerializer):
    """Base serializer for test management models"""
    pass

class TestCategorySerializer(ValidatedModelSerializer):
    """
    Serializer for TestCategory List and Create operations
    """
    test_case_count = serializers.SerializerMethodField()
    
    class Meta(BaseMeta):
        model = TestCategory
        fields = "__all__"

    def get_test_case_count(self, obj):
        request = self.context.get('request')
        user = request.user if request else None
        test_cases = obj.test_cases.all()
        if user and not user.is_superuser:
            test_cases = test_cases.filter(created_by=user)
        return test_cases.count()    

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
    test_type = serializers.CharField(source='get_test_type_display', read_only=True)

    class Meta:
        model = TestCase
        fields = (
            "id",
            "name",
            "test_case_id",
            "test_type",
            "is_active",
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

class TestSuiteCaseSerializer(serializers.ModelSerializer):
    """Serializer for TestSuiteCase (join table with order)"""
    test_case_name = serializers.CharField(source='test_case.name', read_only=True)
    test_case_id = serializers.CharField(source='test_case.test_case_id', read_only=True)
    
    class Meta:
        model = TestSuiteCase
        fields = ['id', 'test_case', 'test_case_name', 'test_case_id', 'order', 'created', 'modified']
        read_only_fields = ['id', 'created', 'modified', 'test_case_name', 'test_case_id']



class TestSuiteCaseDetailSerializer(serializers.ModelSerializer):
    """
    Nested serializer for test cases inside a group detail response
    """
    category_name = serializers.CharField(
        source="test_case.category.name", read_only=True
    )
    test_type = serializers.SerializerMethodField()
    # Pull fields up from the nested test_case
    id = serializers.UUIDField(source="test_case.id", read_only=True)
    name = serializers.CharField(source="test_case.name", read_only=True)
    test_case_id = serializers.CharField(source="test_case.test_case_id", read_only=True)
    category = serializers.UUIDField(source="test_case.category_id", read_only=True)
    is_active = serializers.BooleanField(source="test_case.is_active", read_only=True)

    class Meta:
        model = TestSuiteCase
        fields = (
            "id",
            "name",
            "test_case_id",
            "category",
            "category_name",
            "test_type",
            "is_active",
            "order",
        )

    def get_test_type(self, obj):
        return TestTypeChoices(obj.test_case.test_type).label


class TestSuiteSerializer(ValidatedModelSerializer):
    """
    Serializer for TestSuite List and Create/Update.
    Accepts test_case_ids[] for M2M write.
    """
    test_case_count = serializers.SerializerMethodField()
    test_case_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
        default=list,
    )

    class Meta(BaseMeta):
        model = TestSuite
        fields = (
            "id",
            "name",
            "description",
            "is_active",
            "test_case_count",
            "test_case_ids",   # write-only, accepted on POST/PUT/PATCH
            "created",
            "modified",
        )

    def get_test_case_count(self, obj):
        return obj.test_cases.count()

    # ── pop test_case_ids before ValidatedModelSerializer hits _meta.get_field ──
    def validate(self, attrs):
     self._test_case_ids = attrs.pop("test_case_ids", None)

     # Require on create
     if not self.instance and not self._test_case_ids:
          raise serializers.ValidationError({
               "test_case_ids": _("At least one test case is required when creating a test group.")
          })

     # Require on update only if explicitly sent as empty
     if self.instance and self._test_case_ids is not None and len(self._test_case_ids) == 0:
          raise serializers.ValidationError({
               "test_case_ids": _("At least one test case is required when updating a test group.")
          })

     return super().validate(attrs)



    # ── CREATE ──
    def create(self, validated_data):
        request = self.context["request"]
        validated_data["created_by"] = request.user
        instance = super().create(validated_data)
        self._sync_test_cases(instance, self._test_case_ids)
        return instance

    # ── UPDATE (PUT / PATCH) ──
    def update(self, instance, validated_data):
     instance = super().update(instance, validated_data)
     if self._test_case_ids is not None:
          self._sync_test_cases(instance, self._test_case_ids)
     return instance

    # ── helper: create TestSuiteCase rows ──
    @staticmethod
    def _sync_test_cases(suite, test_case_ids):
        # Validate all IDs exist
        existing = set(
            TestCase.objects.filter(id__in=test_case_ids).values_list("id", flat=True)
        )
        missing = set(test_case_ids) - existing
        if missing:
            raise serializers.ValidationError(
                {"test_case_ids": f"Test case(s) not found: {missing}"}
            )
        # Clear old through-rows, re-create with order
        TestSuiteCase.objects.filter(test_suite=suite).delete()
        TestSuiteCase.objects.bulk_create([
            TestSuiteCase(test_suite=suite, test_case_id=tc_id, order=idx + 1)
            for idx, tc_id in enumerate(test_case_ids)
        ])


class TestSuiteDetailSerializer(ValidatedModelSerializer):
    """
    Serializer for TestSuite Retrieve (GET detail)
    """
    test_case_count = serializers.SerializerMethodField()
    test_cases_detail = serializers.SerializerMethodField()

    class Meta(BaseMeta):
        model = TestSuite
        fields = (
            "id",
            "name",
            "description",
            "is_active",
            "test_case_count",
            "test_cases_detail",
            "created",
            "modified",
        )

    def get_test_case_count(self, obj):
        return obj.test_cases.count()

    def get_test_cases_detail(self, obj):
        suite_cases = obj.suite_cases.select_related(
            "test_case", "test_case__category"
        ).order_by("order")
        return TestSuiteCaseDetailSerializer(
            suite_cases, many=True, context=self.context
        ).data


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



class TestDeviceGroupListSerializer(FilterSerializerByOrgManaged, ValidatedModelSerializer):
    """
    Serializer for TestDeviceGroup List operations
    Shows summary information without nested devices
    """
    organization_name = serializers.CharField(
        source="organization.name",
        read_only=True,
        label=_("Organization Name")
    )
    device_count = serializers.SerializerMethodField(
        label=_("Total Devices")
    )

    class Meta(BaseMeta):
        model = TestDeviceGroup
        fields = (
            "id",
            "name",
            "description",
            "organization",
            "organization_name",
            "device_count",
            "created",
            "modified",
        )
        read_only_fields = BaseMeta.read_only_fields + [
            "organization_name",
            "device_count",
        ]

    def get_device_count(self, obj):
        """
        Return count of active devices in this group
        (excludes deleted devices)
        """
        return obj.devices.filter(device__is_deleted=False).count()


class DeviceForGroupSerializer(serializers.ModelSerializer):
    """
    Minimal serializer for Device objects
    Used when listing devices available to add to a group
    """
    organization_name = serializers.CharField(
        source="organization.name",
        read_only=True
    )

    class Meta:
        model = Device
        fields = (
            "id",
            "name",
            "organization",
            "organization_name",
            "model",
            "is_deleted",
        )
        read_only_fields = fields


class TestDeviceGroupDeviceSerializer(serializers.ModelSerializer):
    """
    Nested serializer for devices inside a group detail response
    """
    device_name = serializers.CharField(
        source="device.name",
        read_only=True
    )
    device_model = serializers.CharField(
        source="device.model",
        read_only=True,
        allow_null=True
    )
    organization_name = serializers.CharField(
        source="group.organization.name",
        read_only=True
    )

    class Meta:
        model = load_model("TestDeviceGroupDevice")
        fields = (
            "id",
            "device",
            "device_name",
            "device_model",
            "organization_name",
            "created",
            "modified",
        )
        read_only_fields = fields


class TestDeviceGroupDetailSerializer(FilterSerializerByOrgManaged, ValidatedModelSerializer):
    """
    Serializer for TestDeviceGroup Detail operations
    Includes nested devices list
    """
    organization_name = serializers.CharField(
        source="organization.name",
        read_only=True,
        label=_("Organization Name")
    )
    device_count = serializers.SerializerMethodField(
        label=_("Total Devices")
    )
    devices_detail = serializers.SerializerMethodField(
        label=_("Devices in Group")
    )
    
    # Write-only field for adding/updating devices
    device_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
        label=_("Device IDs to add to group"),
        help_text=_("Array of device UUIDs to add to this group")
    )

    class Meta(BaseMeta):
        model = TestDeviceGroup
        fields = (
            "id",
            "name",
            "description",
            "organization",
            "organization_name",
            "device_count",
            "devices_detail",
            "device_ids",  # write-only
            "created",
            "modified",
        )
        read_only_fields = BaseMeta.read_only_fields + [
            "organization_name",
            "device_count",
            "devices_detail",
        ]

    def get_device_count(self, obj):
        """Count active devices in group"""
        return obj.devices.filter(device__is_deleted=False).count()

    def get_devices_detail(self, obj):
        """Get detailed info about all devices in group"""
        devices = obj.devices.select_related(
            "device",
            "group__organization"
        ).filter(device__is_deleted=False).order_by("device__name")
        
        return TestDeviceGroupDeviceSerializer(
            devices,
            many=True,
            context=self.context
        ).data
    
    def validate_name(self, value):
     if len(value) < 3:
          raise serializers.ValidationError(
               _("Group name must be between 3 and 100 characters")
          )
     return value

    def validate_device_ids(self, value):
     """Validate that all device IDs exist and belong to the group's organization"""
     # Don't validate empty here — handled in validate()
     if not value:
          return value

     user = self.context["request"].user
     organization = self.instance.organization if self.instance else None

     if not organization and "organization" in self.initial_data:
          org_id = self.initial_data["organization"]
          try:
               organization = Organization.objects.get(id=org_id)
          except Organization.DoesNotExist:
               raise serializers.ValidationError(_("Organization not found"))

     if not organization:
          raise serializers.ValidationError(
               _("Organization must be specified when adding devices")
          )

     # Validate all IDs exist
     existing_devices = set(
          Device.objects.filter(
               id__in=value,
               is_deleted=False
          ).values_list("id", flat=True)
     )
     missing = set(value) - existing_devices
     if missing:
          raise serializers.ValidationError(  # plain string, not nested dict
               _("Device(s) not found: {}").format(missing)
          )

     # Validate all devices belong to the same organization
     devices = Device.objects.filter(id__in=value)
     org_mismatch = list(devices.exclude(organization=organization).values_list("name", flat=True))
     if org_mismatch:
          raise serializers.ValidationError(  # plain string
               _("The following device(s) do not belong to the selected organization: {}").format(
                    ", ".join(org_mismatch)
               )
          )

     # Non-superusers: devices must be from organizations they manage
     if not user.is_superuser:
          unmanaged = list(devices.exclude(
               organization_id__in=user.organizations_managed
          ).values_list("name", flat=True))
          if unmanaged:
               raise serializers.ValidationError(  # plain string
                    _("You don't have permission to add these device(s): {}").format(
                         ", ".join(unmanaged)
                    )
               )

     return value



    def validate_organization(self, value):
        """
        Validate that user has access to the organization
        Superusers can access all, non-superusers only managed orgs
        """
        user = self.context["request"].user
        
        # Superuser can access any organization
        if user.is_superuser:
            return value
        
        # Non-superuser can only manage their own organizations
        if str(value.id) not in user.organizations_managed:
            raise serializers.ValidationError(
                _("You don't have permission to manage this organization")
            )
        
        return value

    def validate(self, attrs):
     self._device_ids = attrs.pop("device_ids", None)  # None = not sent, [] = sent empty

     # Require on create
     if not self.instance and not self._device_ids:
          raise serializers.ValidationError({
               "device_ids": _("At least one device is required when creating a device group.")
          })

     # Require on update only if explicitly sent as empty
     if self.instance and self._device_ids is not None and len(self._device_ids) == 0:
          raise serializers.ValidationError({
               "device_ids": _("At least one device is required when updating a device group.")
          })

     return super().validate(attrs)



    def create(self, validated_data):
     instance = super().create(validated_data)
     TestDeviceGroupDetailSerializer._sync_devices(instance, self._device_ids)
     return instance

    def update(self, instance, validated_data):
     instance = super().update(instance, validated_data)
     # Only sync if device_ids was explicitly provided in request
     if self._device_ids is not None:
          self._sync_devices(instance, self._device_ids)
     return instance

    @staticmethod
    def _sync_devices(group, device_ids):
        """
        Helper: Create/update TestDeviceGroupDevice entries
        Clears old devices and recreates with new ones
        """
        TestDeviceGroupDevice = load_model("TestDeviceGroupDevice")
        
        if not device_ids:
            # If empty list sent, clear all devices
            TestDeviceGroupDevice.objects.filter(group=group).delete()
            return

        # Validate all IDs exist (double-check)
        existing = set(
            Device.objects.filter(id__in=device_ids).values_list("id", flat=True)
        )
        missing = set(device_ids) - existing
        if missing:
            raise serializers.ValidationError(
                {"device_ids": _("Device(s) not found: {}").format(missing)}
            )

        # Clear old entries and recreate
        TestDeviceGroupDevice.objects.filter(group=group).delete()
        
        # Bulk create new entries
        TestDeviceGroupDevice.objects.bulk_create([
            TestDeviceGroupDevice(group=group, device_id=dev_id)
            for dev_id in device_ids
        ], ignore_conflicts=True)


class TestDeviceGroupCreateSerializer(FilterSerializerByOrgManaged, ValidatedModelSerializer):
    """
    Serializer for TestDeviceGroup Create operations
    Includes device_ids write-only field
    """
    device_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
        default=list,
        label=_("Device IDs"),
        help_text=_("Array of device UUIDs to add to this group")
    )

    class Meta(BaseMeta):
        model = TestDeviceGroup
        fields = (
            "id",
            "name",
            "description",
            "organization",
            "device_ids",
            "created",
            "modified",
        )

    def validate_device_ids(self, value):
        """Validate all device IDs exist and belong to organization"""
        if not value:
            return value

        user = self.context["request"].user
        org_id = self.initial_data.get("organization")
        
        if not org_id:
            raise serializers.ValidationError(
                _("Organization must be specified")
            )

        try:
         organization = Organization.objects.get(id=org_id)
        except Organization.DoesNotExist:
         raise serializers.ValidationError(_("Organization not found"))

        # Check devices exist
        existing = set(
            Device.objects.filter(
                id__in=value,
                is_deleted=False
            ).values_list("id", flat=True)
        )
        missing = set(value) - existing
        if missing:
            raise serializers.ValidationError(
                _("Device(s) not found: {}").format(missing)
            )

        # Check devices belong to org
        devices = Device.objects.filter(id__in=value)
        org_mismatch = devices.exclude(organization=organization)
        if org_mismatch.exists():
            raise serializers.ValidationError(
                _("Not all devices belong to the selected organization")
            )

        # Check user permissions
        if not user.is_superuser:
            if str(organization.id) not in user.organizations_managed:
                raise serializers.ValidationError(
                    _("You don't have permission to manage this organization")
                )

        return value


    def validate_organization(self, value):
     user = self.context["request"].user
     if user.is_superuser:
          return value
     if str(value.id) not in user.organizations_managed:
          raise serializers.ValidationError(
               _("You don't have permission to manage this organization")
          )
     return value
    
    def validate_organization(self, value):
        """Validate user has access to organization"""
        user = self.context["request"].user
        
        if user.is_superuser:
            return value
        
        if str(value.id) not in user.organizations_managed:
            raise serializers.ValidationError(
                _("You don't have permission to manage this organization")
            )
        
        return value

    def validate(self, attrs):
        """Pop device_ids before model validation"""
        self._device_ids = attrs.pop("device_ids", [])
        return super().validate(attrs)

    def create(self, validated_data):
        """Create group and add devices"""
        instance = super().create(validated_data)
        TestDeviceGroupDetailSerializer._sync_devices(instance, self._device_ids)
        return instance
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
    created_by = serializers.ReadOnlyField(source="created_by.username")
    category_name = serializers.CharField(source="category.name", read_only=True)
    test_type_display = serializers.CharField(source='get_test_type_display', read_only=True)


    test_case_id_validators = [
        RegexValidator(
            regex=r'^[A-Za-z][A-Za-z0-9_\-.:/]*$',
            message=_(
                "Test Case ID must start with a letter and contain only "
                "letters, numbers, _, -, ., :, /"
            ),
        ),
        MinLengthValidator(3, message=_("Test Case ID must be at least 3 characters long.")),
        MaxLengthValidator(20, message=_("Test Case ID must not exceed 20 characters.")),
    ]

    test_case_id = serializers.CharField(
        validators=test_case_id_validators
    )
    class Meta:
        model = TestCase
        fields = [
            "id",
            "name",
            "test_case_id",
            "category",
            "category_name",
            "description",
            "test_type",
            "test_type_display",
            "params",
            "python_script",
            "robot_script",
            "is_active",
            "is_configuration_push_required",
            "script_push_status",
            "created", 
            "modified",
            "created_by",
        ]
        read_only_fields = [
            "script_push_status",
            "created",
            "modified",
            "category_name",
            "test_type_display"
        ]
    def validate(self, attrs):
        """
        Reuse model clean() logic (same as admin)
        """
        request = self.context.get("request")
        user = request.user if request else None

        if self.instance and "test_case_id" in attrs:
            if attrs["test_case_id"] != self.instance.test_case_id:
                raise serializers.ValidationError({
                    "test_case_id": "Test Case ID cannot be modified after creation."
                })
              
        if self.instance and "test_type" in attrs:
            if attrs["test_type"] != self.instance.test_type:
                raise serializers.ValidationError({
                    "test_type": "Test Type cannot be modified after creation."
                })

        if "is_system_test_case" in attrs:
            if not user or not user.is_superuser:
                raise serializers.ValidationError({
                    "is_system_test_case": "Only superusers can set this field."
                })
        
        if self.instance and "is_system_test_case" in attrs:
            if attrs["is_system_test_case"] != self.instance.is_system_test_case:
                raise serializers.ValidationError({
                    "test_type": "is_system_test_case cannot be modified after creation."
                })
                
        if self.instance:
            instance = self.instance
            for attr, value in attrs.items():
                setattr(instance, attr, value)
        else:
            instance = TestCase(**attrs)
        
        

        try:
            instance.clean()
        except ValidationError as e:
            raise serializers.ValidationError(e.message_dict)
        
        is_system_test_case= attrs.get("is_system_test_case", instance.is_system_test_case)
        test_type = attrs.get(
        "test_type",
        instance.test_type if self.instance else None
        )
        python_script = attrs.get(
            "python_script",
            instance.python_script if self.instance else None
        )
        robot_script = attrs.get(
            "robot_script",
            instance.robot_script if self.instance else None
        )
        test_case_id = attrs.get(
            "test_case_id",
            instance.test_case_id if self.instance else None
        )
        # DEVICE test
        if not python_script:
            if (
                user
                and user.is_superuser
                and is_system_test_case
                and test_case_id
            ):
                rel_path= f"test_case_robot/{test_case_id}.py" if test_type== TestTypeChoices.ROBOT_FRAMEWORK else f"test_case/{test_case_id}.py"
                abs_path= os.path.join(settings.MEDIA_ROOT, rel_path)
                if not os.path.exists(abs_path):
                    raise serializers.ValidationError({
                        "python_script":f"System Python script not found for the given test case with id '{test_case_id}' "
                    }  
                    )
                python_script = rel_path
                attrs["python_script"] = python_script
            else:
                raise serializers.ValidationError({
                    "python_script": "Python script is required."
                })

        if test_type == TestTypeChoices.AGENT:
            if robot_script:
                raise serializers.ValidationError({
                    "robot_script": "Robot script is not allowed for Device tests."
                })

        # ROBOT test
        if test_type == TestTypeChoices.ROBOT_FRAMEWORK:
            if not robot_script:
                if (
                    user
                    and user.is_superuser
                    and is_system_test_case
                    and test_case_id
                ):
                    rel_path= f"test_case_robot/{test_case_id}.robot"
                    abs_path= os.path.join(settings.MEDIA_ROOT, rel_path)
                    if not os.path.exists(abs_path):
                        raise serializers.ValidationError({
                            "robot_script":f"System Robot Framework script not found for the given test case with id '{test_case_id}'"
                            }
                        )
                    robot_script = rel_path
                    attrs["robot_script"] = robot_script
                    return attrs
                else:
                    raise serializers.ValidationError({
                        "robot_script": "Robot script is required for Robot tests."
                    })
            
            attrs["robot_script"] = update_robot_file_tag(
                robot_script,
                test_case_id
            )

        return attrs
    
    def validate_python_script(self, file):
        if not file:
            return file

        if not file.name.endswith(".py"):
            raise serializers.ValidationError("Only .py files are allowed")

        try:
            content = file.read().decode("utf-8")
            compile(content, file.name, "exec")
        except SyntaxError as e:
            raise serializers.ValidationError(
                f"Python syntax error at line {e.lineno}: {e.msg}"
            )
        except UnicodeDecodeError:
            raise serializers.ValidationError("Python script must be UTF-8 encoded")

        file.seek(0)
        return file
    
    def validate_robot_script(self, file):
        if not file:
            return file

        if not file.name.endswith(".robot"):
            raise serializers.ValidationError("Only .robot files are allowed")

        content = file.read().decode("utf-8")

        if "*** Test Cases ***" not in content:
            raise serializers.ValidationError(
                "Invalid Robot file: missing '*** Test Cases ***' section"
            )

        # Write back modified content
        file.seek(0)
        file.file.write(content.encode("utf-8"))
        file.seek(0)

        return file








class TestCaseDetailSerializer(TestCaseSerializer):
    suite_count = serializers.ReadOnlyField()
    execution_count = serializers.ReadOnlyField()
    is_deletable = serializers.ReadOnlyField()

    class Meta(TestCaseSerializer.Meta):
        fields = TestCaseSerializer.Meta.fields + [
            "suite_count",
            "execution_count",
            "is_deletable",
        ]

class TestCaseImportSerializer(serializers.Serializer):
    file = serializers.FileField()

    def validate_file(self, file):
        name = file.name.lower()
        content_type = file.content_type

        if not (
            name.endswith(".xlsx") or name.endswith(".csv")
        ):
            raise serializers.ValidationError(
                "Only .xlsx or .csv files are supported."
            )

        return file


class TestSuiteCaseSerializer(serializers.ModelSerializer):
    """Serializer for TestSuiteCase through model"""
    test_case_detail = TestCaseListSerializer(source="test_case", read_only=True)
    
    class Meta:
        model = TestSuiteCase
        fields = ["id", "test_case", "test_case_detail", "order"]


class TestSuiteListSerializer(TestSuiteSerializer):
    """Lightweight serializer for list views"""
    
    class Meta(BaseMeta):
        model = TestSuite
        fields = [
            "id",
            "name",
            "is_active",
            "test_case_count",
            "execution_count",
            "created",
            "modified",
        ]
        read_only_fields = BaseMeta.read_only_fields + [
            "test_case_count",
            "execution_count",
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

    status_display = serializers.CharField(read_only=True)
    active_device_count = serializers.IntegerField(read_only=True)
    is_re_execution = serializers.BooleanField(read_only=True)

    artifacts = ExecutionArtifactSerializer(many=True, read_only=True)
    test_selection_type = serializers.SerializerMethodField()
    device_selection = serializers.SerializerMethodField()
    execution_status = serializers.SerializerMethodField()
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
            "status_display",
            "active_device_count",
            "is_re_execution",

            "created",
            "modified",
            "notification_emails",
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

    def get_device_selection(self, obj):
        if obj.device_selection == 0:
            return "Individual"
        elif obj.device_selection == 1:
            return "Device Group"

    def get_test_selection_type(self, obj):
        if obj.test_selection_type == 0:
            return "Individual"
        elif obj.test_selection_type == 1:
            return "Test Group"

    def get_execution_status(self, obj):
        if obj.execution_status == 0:
            return "Created"
        elif obj.execution_status == 1:
            return "Execution Progress"
        elif obj.execution_status == 2:
            return "Partially Completed"
        elif obj.execution_status == 3:
            return "Completed"

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

class TestSuiteExecutionCreateSerializer(serializers.Serializer):
    ssh_enabled = getattr(settings, 'TEST_MANAGEMENT_SSH_ENABLED', True)
    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(required=True, allow_blank=False, max_length=50)
    individual_test_cases = serializers.PrimaryKeyRelatedField(
        queryset=TestCase.objects.all(),
        many=True,
        required=False
    )
    test_suite = serializers.PrimaryKeyRelatedField(
        queryset=TestSuite.objects.all(),
        many=False,
        required=False,
    )

    devices = serializers.ListField(
        child=serializers.DictField(
            child=serializers.CharField()
        ),
        write_only=True,
        help_text="""
        List of devices with communication protocol.
        Example:
        [
          {"device_id": "uuid", "connection_protocol": "MQTT"},
          {"device_id": "uuid", "connection_protocol": "SSH"}
        ]
        """
    )

    TEST_SELECTION_MAP = {
        "individual": 0,
        "group": 1,
    }

    test_selection_type = serializers.ChoiceField(
        choices=[
            ("individual", "Individual Test Cases"),
            ("group", "Test Group"),
        ]
    )

    notification_emails = serializers.ListField(
        child=serializers.EmailField(),
        required=False,
        allow_empty=True,
        write_only=True,
    )

    class Meta:
        model = load_model("TestSuiteExecution")
        fields = [
            "id",
            "name",
            "test_selection_type",
            "test_suite",
            "individual_test_cases",
            "devices",
            "notification_emails",
        ]

    def create(self, validated_data):
        # Map string values to integer values
        validated_data["test_selection_type"] = self.TEST_SELECTION_MAP[
            validated_data["test_selection_type"]
        ]
        test_cases_data = validated_data.pop("individual_test_cases", [])
        emails = validated_data.pop("notification_emails", [])
        validated_data["notification_emails"] = ",".join(emails)

        device_list = validated_data.pop("devices", [])
        # Set created_by from request user
        request = self.context.get('request')
        if request and request.user:
            validated_data['created_by'] = request.user
        validated_data['device_count'] = len(device_list)
        execution = TestSuiteExecution.objects.create(**validated_data)
        if validated_data["test_selection_type"] == 0 and test_cases_data:
            execution.individual_test_cases.set(test_cases_data)
            test_cases_id = [str(tc.id) for tc in test_cases_data]
            execution.test_case_execution_order = test_cases_id
            execution.testcase_count = len(test_cases_data)
            execution.save()
        

        device_map = {
            device.id: device
            for device in Device.objects.filter(
                id__in=[UUID(d["device_id"]) for d in device_list]
            )
        }

        if len(device_map) != len(device_list):
            raise serializers.ValidationError(
                {"devices": "One or more device IDs are invalid."}
            )

        for device_data in device_list:
            TestSuiteExecutionDevice.objects.create(
                test_suite_execution=execution,
                device=device_map.get(UUID(device_data["device_id"])),
                connection_protocol=device_data["connection_protocol"],
                status="pending",
            )

        return execution

    def update(self, instance, validated_data):
        individual_test_cases = validated_data.pop("individual_test_cases", None)
        device_list = validated_data.pop("devices", [])
        ssh_enabled = getattr(settings, 'TEST_MANAGEMENT_SSH_ENABLED', False)
        validated_data["test_selection_type"] = self.TEST_SELECTION_MAP[
            validated_data["test_selection_type"]
        ]

        # update normal fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        device_map = {
            device.id: device
            for device in Device.objects.filter(
                id__in=[UUID(d["device_id"]) for d in device_list]
            )
        }

        for device_data in device_list:
         if not ssh_enabled and device_data.get("connection_protocol") == 1:
             raise serializers.ValidationError(
                  "SSH protocol is disabled in this environment."
             )        


        if len(device_map) != len(device_list):
            raise serializers.ValidationError(
                {"devices": "One or more device IDs are invalid."}
            )
        if len(device_list) > 0:
            TestSuiteExecutionDevice.objects.filter(
                test_suite_execution=instance
            ).delete()

            
            for device_data in device_list:
                TestSuiteExecutionDevice.objects.create(
                    test_suite_execution=instance,
                    device=device_map.get(UUID(device_data["device_id"])),
                    connection_protocol=device_data["connection_protocol"],
                    status="pending",
                )

        # update M2M safely
        if individual_test_cases is not None:
            instance.individual_test_cases.set(individual_test_cases)

        return instance

    # ---------- VALIDATION ----------
    def validate_devices(self, devices):
        ssh_enabled = getattr(settings, 'TEST_MANAGEMENT_SSH_ENABLED', False)
        PROTOCOL_MAP = {
            "MQTT": 0,
            "SSH": 1,
        }
        validated = []

        for device in devices:
            if "device_id" not in device:
                raise serializers.ValidationError("device_id is required")

            if "connection_protocol" not in device:
                raise serializers.ValidationError("connection_protocol is required")

            protocol = device["connection_protocol"]

            if protocol not in PROTOCOL_MAP:
                raise serializers.ValidationError(
                    f"Invalid protocol {protocol}. Allowed: MQTT, SSH"
                )
            if not ssh_enabled and PROTOCOL_MAP[protocol] == 1:
             raise serializers.ValidationError(
                "SSH protocol is disabled in this environment."
             )

            validated.append({
                "device_id": device["device_id"],
                "connection_protocol": PROTOCOL_MAP[protocol],
            })

        return validated

    def validate(self, attrs):
        test_selection_type = attrs.get(
            "test_selection_type",
            getattr(self.instance, "test_selection_type", None)
        )
        test_suite = attrs.get("test_suite")
        individual_cases = attrs.get("individual_test_cases")

        if test_selection_type  in [1, "1", "group"] and not test_suite:
            raise serializers.ValidationError({
                "test_suite": "Test group is required when test_selection_type is 'Group'."
            })

        if test_selection_type in [0, "0", "individual"] and not individual_cases:
            raise serializers.ValidationError({
                "individual_test_cases": "At least one test case is required for individual selection."
            })
        if test_selection_type  in [0, "0", "individual"] and len(individual_cases) == 0:
            raise serializers.ValidationError({
                "individual_test_cases": "At least one test case is required for individual selection."
            })

        return attrs

class ReExecuteSelectedTestsSerializer(serializers.Serializer):
    device_tests_info = serializers.DictField(
        child=serializers.ListField(
            child=serializers.CharField(),
            min_length=1
        )
    )

    def validate_device_tests_info(self, value):
        if not value:
            raise serializers.ValidationError(
                "No tests selected for re-execution."
            )
        execution = self.context.get("execution")
        device_executions = TestSuiteExecutionDevice.objects.filter(
            test_suite_execution=execution
        ).select_related('device')
        errors = {}
        org_devices = [str(device_execution.device.id)
                       for device_execution in device_executions]

        for device_id, test_case_ids in value.items():
            device = Device.objects.get(id=device_id)
            if not device:
                raise serializers.ValidationError(
                    "Device not found for given UUID: {device_id}"
                )
            if device_id not in org_devices:
                errors[device_id] = "Device not found in this execution."
                continue
            invalid_tests = []
            if execution.test_selection_type == 0:
                invalid_tests = [
                    str(tc_id)
                    for tc_id in test_case_ids
                    if not execution.individual_test_cases.filter(id=tc_id).exists()
                ]
            if execution.test_selection_type == 1:
                invalid_tests = [
                    str(tc_id)
                    for tc_id in test_case_ids
                    if not execution.test_suite.test_cases.filter(id=tc_id).exists()
                ]
            if invalid_tests:
                errors[device_id] = (
                    f"Invalid test case(s): {', '.join(invalid_tests)}"
                )

        if errors:
            raise serializers.ValidationError(errors)
        return value

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
            "created",
            "modified",
        ]
        read_only_fields = BaseMeta.read_only_fields + [
            "is_executed",
            "device_count",
            # "status_summary",
        ]
    
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


class TestSuiteExecutionListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views"""
    
    class Meta(BaseMeta):
        model = TestSuiteExecution
        fields = [
            "id",
            "name",
            "device_count",
            "testcase_count",
            "created",
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

    def validate_confirm(self, value):
        """Ensure deletion is confirmed"""
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

class EmptySerializer(serializers.Serializer):
    pass