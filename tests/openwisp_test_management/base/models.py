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
    description = models.TextField(
        _("description"),
        blank=True,
        help_text=_("Detailed description of what tests in this category do")
    )
    code = models.CharField(  # ✅ Code field without uniqueness
        _("code"),
        max_length=64,
        blank=True,
        help_text=_("Optional code for this category")
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
        # This will be implemented when TestCase model is added
        return 0

    @property
    def is_deletable(self):
        """Check if category can be deleted"""
        # Categories with test cases cannot be deleted
        return self.test_case_count == 0