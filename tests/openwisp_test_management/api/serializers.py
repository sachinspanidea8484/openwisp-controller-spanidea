from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from openwisp_users.api.mixins import FilterSerializerByOrgManaged
from openwisp_utils.api.serializers import ValidatedModelSerializer

from ..swapper import load_model

TestCategory = load_model("TestCategory")


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