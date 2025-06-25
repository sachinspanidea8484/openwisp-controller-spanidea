from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from openwisp_users.api.mixins import FilterSerializerByOrgManaged
from openwisp_utils.api.serializers import ValidatedModelSerializer

from ..swapper import load_model

TestCategory = load_model("TestCategory")
TestCase = load_model("TestCase")
TestSuite = load_model("TestSuite")
TestSuiteCase = load_model("TestSuiteCase")


class BaseMeta:
    read_only_fields = ["created", "modified"]


class BaseSerializer(FilterSerializerByOrgManaged, ValidatedModelSerializer):
    """Base serializer for test management models"""
    pass


class TestCategorySerializer(BaseSerializer):
    """Serializer for TestCategory model"""
    test_case_count = serializers.IntegerField(read_only=True)
    
    class Meta(BaseMeta):
        model = TestCategory
        fields = [
            "id",
            "organization",
            "name",
            "code",
            "description",
            "test_case_count",
            "created",
            "modified",
        ]
        read_only_fields = BaseMeta.read_only_fields + ["test_case_count"]

    def validate_organization(self, value):
        """Only superusers can create shared categories (organization=None)"""
        request = self.context.get("request")
        if not value and request and not request.user.is_superuser:
            raise serializers.ValidationError(
                _("Only superusers can create shared test categories")
            )
        return value

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
            "organization",
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
        fields = ["id", "name", "organization"]
        read_only_fields = fields


class TestCaseSerializer(ValidatedModelSerializer):
    """Serializer for TestCase model"""
    category_detail = TestCategoryRelationSerializer(source="category", read_only=True)
    organization = serializers.SerializerMethodField()
    
    class Meta(BaseMeta):
        model = TestCase
        fields = [
            "id",
            "name",
            "test_case_id",
            "category",
            "category_detail",
            "description",
            "is_active",
            "organization",
            "created",
            "modified",
        ]
        read_only_fields = BaseMeta.read_only_fields + [
            "organization",
        ]

    def get_organization(self, obj):
        """Get organization from category"""
        if obj.category and obj.category.organization:
            return {
                "id": str(obj.category.organization.id),
                "name": obj.category.organization.name,
                "slug": obj.category.organization.slug,
            }
        return None

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
    
    class Meta(BaseMeta):
        model = TestCase
        fields = [
            "id",
            "name",
            "test_case_id",
            "category",
            "category_name",
            "is_active",
            "created",
            "modified",
        ]
        read_only_fields = BaseMeta.read_only_fields + [
            "category_name",
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
    organization = serializers.SerializerMethodField()
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
            "organization",
            "test_case_count",
            "execution_count",
            "created",
            "modified",
        ]
        read_only_fields = BaseMeta.read_only_fields + [
            "test_case_count",
            "execution_count",
            "organization",
        ]

    def get_organization(self, obj):
        """Get organization from category"""
        if obj.category and obj.category.organization:
            return {
                "id": str(obj.category.organization.id),
                "name": obj.category.organization.name,
                "slug": obj.category.organization.slug,
            }
        return None

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
        
        # Validate all test cases belong to the same category
        test_cases = TestCase.objects.filter(id__in=value)
        
        if test_cases.count() != len(value):
            raise serializers.ValidationError(_("Some test case IDs are invalid"))
        
        for test_case in test_cases:
            if test_case.category != category:
                raise serializers.ValidationError(
                    _(f"Test case '{test_case.name}' does not belong to the selected category")
                )
        
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