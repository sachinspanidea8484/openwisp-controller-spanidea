import logging

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from openwisp_users.mixins import ShareableOrgMixin
from openwisp_utils.base import TimeStampedEditableModel

logger = logging.getLogger(__name__)


class AbstractTestCategory(ShareableOrgMixin, TimeStampedEditableModel):
    """
    Abstract model for Test Categories
    Categories group test cases by type or purpose
    """
    name = models.CharField(
        _("name"),
        max_length=64,
        db_index=True,
        help_text=_("Category name to group related test cases")
    )
    code = models.CharField(  # ✅ Code field without uniqueness
        _("code"),
        max_length=64,
        blank=True,
        help_text=_("Optional code for this category")
    )
    description = models.TextField(
        _("description"),
        blank=True,
        help_text=_("Detailed description of what tests in this category do")
    )

    class Meta:
        abstract = True
        verbose_name = _("Test Category")
        verbose_name_plural = _("Test Categories")
        unique_together = ("name", "organization")
        ordering = ["name"]

    def __str__(self):
        return self.name

    def clean(self):
        """Validate the test category"""
        super().clean()
        if not self.name:
            raise ValidationError({"name": _("Name is required")})
        
        # Check for duplicate names within the same organization
        if self.organization:
            qs = self.__class__.objects.filter(
                name__iexact=self.name,
                organization=self.organization
            ).exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError({
                    "name": _(
                        f"A test category with this name already exists "
                        f"in {self.organization}"
                    )
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def test_case_count(self):
        """Return count of test cases in this category"""
        # Import here to avoid circular imports
        from ..swapper import load_model
        TestCase = load_model("TestCase")
        return TestCase.objects.filter(category=self).count()

    @property
    def is_deletable(self):
        """Check if category can be deleted"""
        # Categories with test cases cannot be deleted
        return self.test_case_count == 0


class AbstractTestCase(TimeStampedEditableModel):
    """
    Abstract model for Test Cases
    Individual test cases that can be executed on devices
    """
    name = models.CharField(
        _("Test Case Name"),
        max_length=128,
        db_index=True,
        help_text=_("Descriptive name for the test case")
    )
    test_case_id = models.CharField(
        _("Test Case ID"),
        max_length=64,
        db_index=True,
        help_text=_("Unique identifier used by devices to execute this test")
    )
    category = models.ForeignKey(
        'test_management.TestCategory',
        on_delete=models.PROTECT,
        related_name='test_cases',
        verbose_name=_("category"),
        help_text=_("Category this test case belongs to")
    )
    description = models.TextField(
        _("description"),
        blank=True,
        help_text=_("Detailed description of what this test does")
    )
    # Additional fields for future use
    is_active = models.BooleanField(
        _("is active"),
        default=True,
        help_text=_("Whether this test case is currently active")
    )


    class Meta:
        abstract = True
        verbose_name = _("Test Case")
        verbose_name_plural = _("Test Cases")
        unique_together = ("category", "name")
        ordering = ["category", "name"]
        indexes = [
            models.Index(fields=["test_case_id"]),
            models.Index(fields=["category", "name"]),
        ]

    def __str__(self):
        return f"{self.category.name} - {self.name}"

    def clean(self):
        """Validate the test case"""
        super().clean()
        
        # Validate required fields
        if not self.name:
            raise ValidationError({"name": _("Test case name is required")})
        
        if not self.test_case_id:
            raise ValidationError({"test_case_id": _("Test Case ID is required")})
        
        # Check for duplicate test_case_id across all organizations
        qs = self.__class__.objects.filter(
            test_case_id=self.test_case_id
        ).exclude(pk=self.pk)
        
        if qs.exists():
            raise ValidationError({
                "test_case_id": _(
                    f"A test case with ID '{self.test_case_id}' already exists"
                )
            })
        
        # Check for duplicate name within the same category
        if self.category_id:
            qs = self.__class__.objects.filter(
                category=self.category,
                name__iexact=self.name
            ).exclude(pk=self.pk)
            
            if qs.exists():
                raise ValidationError({
                    "name": _(
                        f"A test case with this name already exists "
                        f"in category '{self.category.name}'"
                    )
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def organization(self):
        """Get organization from category"""
        return self.category.organization

    @property
    def is_deletable(self):
        """Check if test case can be deleted"""
        # Test cases in suites or with executions cannot be deleted
        return True

    