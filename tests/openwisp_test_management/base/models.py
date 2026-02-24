import logging
from django.utils import timezone
import os

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from openwisp_users.mixins import OrgMixin

from openwisp_utils.base import TimeStampedEditableModel

logger = logging.getLogger(__name__)

from ..private_storage import storage
overwrite_storage= storage.OverwriteStorage()


def rename_script(instance, filename):
    ext= filename.split('.')[1]
    new_name= f"{instance.test_case_id}.{ext}"
    if instance.test_type==1:
        return os.path.join("test_case_robot", new_name)
    else:
        return os.path.join("test_case", new_name)
  

def get_build_directory(instance, filename):
    build_pk = str(instance.name)
    return f"{build_pk}/{filename}"

# ENUM class for test type choice
class TestTypeChoices(models.IntegerChoices):
    ROBOT_FRAMEWORK = 1, _('Robot Framework')
    AGENT = 2, _('Device')

class TestExecutionStatus(models.TextChoices):
    PENDING = 'pending', _('Pending')
    RUNNING = 'running', _('Running')
    SUCCESS = 'success', _('Passed')
    FAILED = 'failed', _('Failed')
    TIMEOUT = 'timeout', _('Timeout')
    CANCELLED = 'cancelled', _('Cancelled')
    ABORTING = 'aborting', _('Aborting')
    ABORTED = 'aborted', _('Aborted')


class AbstractTestCategory(TimeStampedEditableModel):
    """
    Abstract model for Test Categories
    Categories group test cases by type or purpose
    """

    name = models.CharField(
        _("category Name"),
        max_length=50,
        db_index=True,
        unique=True,
        help_text=_("Category name to group related test cases")
    )
    code = models.CharField(
        _("category Code"),
        max_length=50,
        blank=False,  
        help_text=_("Required code for this category") 
    )
    description = models.TextField(
        _("description"),
        max_length=1000,
        help_text=_("Detailed description of what tests in this category do")
    )

    class Meta:
        abstract = True
        verbose_name = _("Test Category")
        verbose_name_plural = _("Test Categories")
        ordering = ["name"]

    def __str__(self):
        return self.name

    def clean(self):
        """Validate the test category"""
        super().clean()
      
        qs = self.__class__.objects.filter(
            name__iexact=self.name
        ).exclude(pk=self.pk)
        if qs.exists():
            raise ValidationError({
                "name": _("A test category with this name already exists")
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
        # Categories with test cases or test suites cannot be deleted
        return self.test_case_count == 0 
    

class AbstractTestCase(TimeStampedEditableModel):
    """
    Abstract model for Test Cases
    Individual test cases that can be executed on devices
    """

    class Status(models.IntegerChoices):
        PENDING = 0, _('Pending')
        COMPLETED = 1, _('Completed')
        FAILED = 2, _('Failed')
        
    name = models.CharField(
        _("Test Case"),
        max_length=50,
        db_index=True,
        help_text=_("Descriptive name for the test case")
    )
    test_case_id = models.CharField(
        _("Test Case ID"),
        max_length=50,
        unique=True,
        db_index=True,
        help_text=_("Unique identifier used by devices to execute this test")
    )
    category = models.ForeignKey(
        'test_management.TestCategory',
        on_delete=models.PROTECT,
        blank=False,  
        related_name='test_cases',
        verbose_name=_("Select Test Category"), 
        help_text=_("Category this test case belongs to")
    )
    description = models.TextField(
        _("Description"),
        max_length=10000,
        help_text=_("Detailed description of what this test does")
    )
    
    is_active = models.BooleanField(
        _("Is Active"),
        default=True,
        help_text=_("Whether this test case is currently active")
    )
    is_configuration_push_required = models.BooleanField(
        _("Is File Required"),
        default=False,
        help_text=_("Whether a file upload is required for this test case")
    )
    is_system_test_case = models.BooleanField(
        _("Is System TestCase"),
        default=False,
        help_text=_("System-managed test case with preconfigured data.")
    )
    test_type = models.IntegerField(
        _("Test Type"),
        choices=TestTypeChoices.choices,
        default=TestTypeChoices.ROBOT_FRAMEWORK,
        help_text=_("Type of test: Robot Framework (1) or Device (2)")
    )
    params = models.JSONField(
        _("Parameters"),
        default=dict,
        blank=True,
        help_text=_("Optional parameters for test case execution in JSON format. "
                    "These parameters can be used to customize test case behavior.")
    )
    python_script= models.FileField(
        _("Python Script"),
        upload_to=rename_script,
        storage= overwrite_storage,
        null=True,
        blank=True
    )
    robot_script = models.FileField(
        _("Robot Script"),
        upload_to=rename_script,
        storage=overwrite_storage,
        null=True,
        blank=True
    )
    
    script_push_status = models.IntegerField(
        choices=Status.choices,
        default=Status.PENDING
    )
    created_by = models.ForeignKey(
        'openwisp_users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_test_cases',
    )
    

    class Meta:
        abstract = True
        verbose_name = _("Test Case")
        verbose_name_plural = _("Test Cases")
        ordering = ["category", "name"]
        indexes = [
            models.Index(fields=["test_case_id"]),
            models.Index(fields=["category", "name"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.category.name})"


    def clean(self):
        """Validate the test case"""
        super().clean()
 

        # Validate JSON params if provided
        if self.params and self.params != {}:
         
        try:
            if not isinstance(self.params, dict):
                raise ValidationError({
                    "params": _("Parameters must be a valid JSON object (key-value pairs).")
                })
            
        except (TypeError, ValueError) as e:
            raise ValidationError({
                "params": _("Parameters must be valid JSON format")
            })
         
        # Check for duplicate test_case_id
        qs = self.__class__.objects.filter(
                test_case_id=self.test_case_id
        ).exclude(pk=self.pk)
        
        if qs.exists():
                raise ValidationError({
                        "test_case_id": _(
                                f"A test case with ID '{self.test_case_id}' already exists"
                        )
                }) 

    def delete(self, *args, **kwargs):
        if not self.is_deletable:
            raise ValidationError(
                "This Test Case cannot be deleted because it is part of a test suite or execution."
            )
        super().delete(*args, **kwargs)      
        
    def save(self, *args, **kwargs):
        # Ensure params is always a dict, never None or empty string
        if self.params in (None, ""):
         self.params = {}

        if (
            self.test_type == TestTypeChoices.AGENT
            and self.python_script
        ):
            self.script_push_status = self.Status.COMPLETED
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def suite_count(self):
        """Return count of test suites containing this test case"""
        return self.test_suites.count()

    @property
    def execution_count(self):
        """Return count of times this test has been executed"""
        
        from ..swapper import load_model

        TestSuiteExecution = load_model("TestSuiteExecution")

        suite_exec_count = TestSuiteExecution.objects.filter(
            test_suite__suite_cases__test_case=self
        ).distinct().count()

        individual_exec_count = TestSuiteExecution.objects.filter(
            individual_test_cases=self
        ).distinct().count()

        return suite_exec_count + individual_exec_count

    @property
    def is_deletable(self):
        """Check if test case can be deleted"""
        # Test cases in suites or with executions cannot be deleted
        return self.suite_count == 0 and self.execution_count == 0


class AbstractTestSuite(TimeStampedEditableModel):
    """
    Abstract model for Test Suites
    Groups test cases for coordinated execution
    """

    name = models.CharField(
        _("Test Group Name"),  
        max_length=50,
        db_index=True,
        help_text=_("Descriptive name for the test group")  
    )
    description = models.TextField(
        _("Description"),
        max_length=1000,
        help_text=_("Detailed description of what this test group does")  
    )
    is_active = models.BooleanField(
        _("Is Active"), 
        default=True,
        help_text=_("Whether this test group is currently active")  
    )
    test_cases = models.ManyToManyField(
        'test_management.TestCase',
        through='test_management.TestSuiteCase',
        related_name='test_suites',  # Keep model relation name same
        verbose_name=_("Test Cases"),  
        help_text=_("Test cases included in this group")  
    )
    created_by = models.ForeignKey(
        'openwisp_users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_test_case_group',
    )

    class Meta:
        abstract = True
        verbose_name = _("Test Group")  
        verbose_name_plural = _("Test Groups")  
        ordering = [ "name"]

    def __str__(self):
        return f"{self.name}"

    def clean(self):
        """Validate the test group"""
        super().clean()
        
        qs = self.__class__.objects.filter(
            name__iexact=self.name
        ).exclude(pk=self.pk)
        if qs.exists():
            raise ValidationError({
                "name": _("A test group with this name already exists")
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def test_case_count(self):
        """Return count of test cases in this group"""
        return self.test_cases.count()

    @property
    def execution_count(self):
     """Return count of times this group has been executed"""
     from ..swapper import load_model
     TestSuiteExecution = load_model("TestSuiteExecution")
     return TestSuiteExecution.objects.filter(test_suite=self).count()

    @property
    def is_deletable(self):
        """Check if test group can be deleted"""
        # Suites with executions cannot be deleted
        return self.execution_count == 0

    def get_ordered_test_cases(self):
        """Get test cases in execution order"""

        from ..swapper import load_model
        TestSuiteCase = load_model("TestSuiteCase")
        return TestSuiteCase.objects.filter(
            test_suite=self
        ).select_related('test_case').order_by('order')


class AbstractTestSuiteCase(TimeStampedEditableModel):
    """
    Abstract model for Test Suite Cases
    Represents the many-to-many relationship between test suites and test cases
    with ordering support
    """

    test_suite = models.ForeignKey(
        'test_management.TestSuite',
        related_name='suite_cases',
        on_delete=models.CASCADE,
        verbose_name=_("Test Group")  
    )
    test_case = models.ForeignKey(
        'test_management.TestCase',
        on_delete=models.CASCADE,
        verbose_name=_("Test Case") 
    )
    order = models.PositiveIntegerField(
        _("order"),
        default=0,
        help_text=_("Execution order of test case within the group") 
    )

    class Meta:
        abstract = True
        verbose_name = _("Test Group Case") 
        verbose_name_plural = _("Test Group Cases") 
        unique_together = ("test_suite", "test_case")
        ordering = ["test_suite", "order", "test_case"]

    def __str__(self):
        return f"{self.test_suite.name} - {self.order}: {self.test_case.name}"

    def clean(self):
        """Validate test group case"""
        super().clean()
        

    def save(self, *args, **kwargs):
        # Auto-assign order if not specified
        if self.order == 0 and self.test_suite_id:
            max_order = self.__class__.objects.filter(
                test_suite=self.test_suite
            ).aggregate(models.Max('order'))['order__max'] or 0
            self.order = max_order + 1
        
        self.full_clean()
        super().save(*args, **kwargs)


class AbstractTestSuiteExecution(TimeStampedEditableModel):
    """
    Abstract model for Test Suite Executions
    Tracks execution of a test suite on multiple devices
    """
   
    DEVICE_SELECTION_CHOICES = (
        (0, _('Individual')),
        (1, _('Device Group')),
    )
    TEST_SELECTION_CHOICES = (
        (0, _('Individual')),
        (1, _('Group')),
    )
    EXECUTION_STATUS_CHOICE= (
        (0, _('Created')),
        (1,_('Execution Progress')),
        (2,_('Partially Completed')),
        (3,_('Completed'))
    )
    name = models.CharField(
        _("Test Execution Name"), 
        max_length=50,
        db_index=True,
        help_text=_("Descriptive name for the test Execution")  
    )
    test_selection_type = models.IntegerField(
        _("test selection type"),
        choices=TEST_SELECTION_CHOICES,
        default=1,  # Default to Test Group for backward compatibility
        db_index=True,
        help_text=_("Select individual test cases or a test Group")
    )
    test_suite = models.ForeignKey(
        'test_management.TestSuite',
        on_delete=models.PROTECT,
        related_name='executions',
        verbose_name=_("Select Test Group"),
        help_text=_("Test Group to execute (required if selection type is 'Test Group')"),
        null=True,
        blank=True,
    )
    individual_test_cases = models.ManyToManyField(
        'test_management.TestCase',
        blank=True,
        related_name='individual_executions',
        verbose_name=_("Select Test Cases"),
        help_text=_("Individual test cases to execute (required if selection type is 'Individual Test Cases')")
    )
    test_case_execution_order = models.JSONField(default=list, blank=True)
    is_executed = models.BooleanField(
        _("is executed"),
        default=False,
        help_text=_("Whether the execution has completed")
    )
    device_count = models.PositiveIntegerField(
        _("device count"),
        default=0,
        help_text=_("Number of devices in this execution")
    )
    completion_email_sent = models.BooleanField(default=False)
    completion_notification_sent= models.BooleanField(default=False)
    notification_emails = models.TextField(
        blank=True,
        help_text="Comma-separated email addresses"
    )
    testcase_count = models.PositiveIntegerField(
        _("test case count"),
        default=0,
        help_text=_("Number of test cases in this execution")
    )
    device_selection = models.IntegerField(
        _("device selection type"),
        choices=DEVICE_SELECTION_CHOICES,
        default=0,
        help_text=_("Type of device selection: Individual or Device Group")
    )
    device_group = models.ForeignKey(
        'test_management.TestDeviceGroup',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='test_executions',
        verbose_name=_("device group"),
        help_text=_("Device group for execution (required if device selection is 'Device Group')")
    )
    execution_status= models.IntegerField(
        _("Execution Status"),
        choices=EXECUTION_STATUS_CHOICE,
        default=0,
        help_text=_("execution status")
    )
    execution_start_time= models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        'openwisp_users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_test_executions',
    )
    parent_execution = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        related_name="re_executions",
        on_delete=models.CASCADE,
        db_index=True,
        help_text=_("Original execution if this is a re-execution")
    )
    re_execution_index = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=_("1 for first re-execution, 2 for second, etc.")
    )
    execution_status = models.IntegerField(
        _("Execution Status"),
        choices=EXECUTION_STATUS_CHOICE,
        default=0,
        help_text=_("execution status")
    )
    execution_start_time = models.DateTimeField(
        null=True,
        blank=True
    )

    class Meta:
        abstract = True
        verbose_name = _("Test Execution")
        verbose_name_plural = _("Test Executions")
        ordering = ["-created"]

    def get_absolute_url(self):
        return f'/admin/test_management/testsuiteexecution/{self.pk}/history/'
    
    def get_selected_test_cases(self):
        if self.test_selection_type ==1 and self.test_suite_id:
            return self.test_suite.test_cases.all()
        else:
            return self.individual_test_cases.all()

    def get_configuration_selected_test_cases(self):
        if self.test_selection_type ==1 and self.test_suite_id:
            return self.test_suite.test_cases.filter(is_configuration_push_required=True)
        else:
            return self.individual_test_cases.filter(is_configuration_push_required=True)
    
    def get_required_artifacts(self):
        from ..swapper import load_model
        TestSuiteExecutionDevice = load_model("TestSuiteExecutionDevice")
        device_ids= (
            TestSuiteExecutionDevice.objects
            .filter(test_suite_execution=self)
            .values_list("device_id", flat=True)
        )
        test_case_ids = (
            self.get_configuration_selected_test_cases()
            .values_list("id", flat=True)
        )
        result = [
            {
                "device_id": str(device_id),
                "testcase_id": str(testcase_id),
            }
            for device_id in device_ids
            for testcase_id in test_case_ids
        ]
        return result
    
    def trigger_mail(self):
        from ..tasks import send_execution_completed_email
        send_execution_completed_email.delay(str(self.pk))

    def save(self, *args, **kwargs):
        is_new = self.pk is None  # check if new execution
        
        # Pre-calc testcase count from suite
        if self.test_selection_type==1 and self.test_suite_id:
            self.testcase_count = self.test_suite.test_case_count

        self.full_clean()
        super().save(*args, **kwargs)

        from ..swapper import load_model
        TestSuiteExecutionDevice = load_model("TestSuiteExecutionDevice")
        TestCaseExecution = load_model("TestCaseExecution")

        if (
            self.execution_status == 3
            and not self.completion_email_sent
            and self.notification_emails
        ):
            self.trigger_mail()

        # Only run auto-population for new executions with device group
        if is_new and self.device_selection == 1 and self.device_group_id:
            if self.test_selection_type==1 and self.test_suite_id:
                for group_device in self.device_group.devices.select_related("device"):
                    device = group_device.device

                    # Create TestSuiteExecutionDevice
                    execution_device, _ = TestSuiteExecutionDevice.objects.get_or_create(
                            test_suite_execution=self,
                            device=device,
                            defaults={"status": "pending"}
                    )

                    # Create TestCaseExecution per TestCase per Device
                    order = 1
                    for tcase in self.test_suite.test_cases.all():
                        TestCaseExecution.objects.get_or_create(
                            test_suite_execution=self,
                            device=device,
                            test_case=tcase,
                            defaults={
                                "execution_order": order,
                                "status": "pending"
                            }
                        )
                        order = order + 1
            else:
                for group_device in self.device_group.devices.select_related("device"):
                    device = group_device.device
                    TestSuiteExecutionDevice.objects.get_or_create(
                        test_suite_execution=self,
                        device=device,
                        defaults={"status": "pending"}
                    )
               
        # Update device_count ALWAYS (single or group)
        self.device_count = TestSuiteExecutionDevice.objects.filter(
            test_suite_execution=self
        ).count()

        if not is_new and self.test_selection_type==0:
            self.testcase_count= self.individual_test_cases.count()


        if not is_new or self.test_selection_type==1:
            # Save again only updating counts to persist them (only for 1 because M2M not saved yet)
            super().save(update_fields=["device_count", "testcase_count"])


    def execute_tests(self):
       
        # Example async call:
        # from .tasks import run_testsuite_task
        # run_testsuite_task.delay(self.pk)
        self.is_executed = True
        self.save(update_fields=["is_executed"])
        
    @property
    def is_re_execution(self):
        return self.parent_execution_id is not None

    @property
    def root_execution(self):
        return self.parent_execution or self
    
    @property
    def status(self):
        """
        Dynamic status based on execution state
        0 = CREATED (not executed)
        1 = EXECUTION PROGRESS (started but in progress)
        2 = PARTIALLY COMPLETED (mix of done + running/pending)
        3 = COMPLETED (all success/failed)
        """

        if not self.pk:
            return 0  # CREATED
    
        from ..swapper import load_model
        scheduledExecution= load_model("ScheduledExecution")
        
        is_scheduled= scheduledExecution.objects.filter(
            execution= self,
            scheduled_time__gt = timezone.now(),
            status=scheduledExecution.Status.PENDING
        ).exists()

        
        if is_scheduled:
            return 4
        
        if not self.is_executed:
            return 0  # CREATED

        from ..swapper import load_model
        TestCaseExecution = load_model("TestCaseExecution")

        executions = TestCaseExecution.objects.filter(test_suite_execution=self)
        if not executions.exists():
            return 1  # EXECUTION PROGRESS but no tests yet

        total = executions.count()
        completed_statuses = [TestExecutionStatus.SUCCESS, TestExecutionStatus.FAILED, TestExecutionStatus.ABORTED, TestExecutionStatus.TIMEOUT]
        incomplete_statuses = [
            TestExecutionStatus.PENDING,
            TestExecutionStatus.RUNNING,
            TestExecutionStatus.CANCELLED,
        ]

        completed_count = executions.filter(status__in=completed_statuses).count()
        incomplete_count = executions.filter(status__in=incomplete_statuses).count()

        if completed_count == total:
            return 3  # COMPLETED
        elif completed_count > 0 and incomplete_count > 0:
            return 2  # PARTIALLY COMPLETED
        else:
            return 1  # EXECUTION PROGRESS
        
    @property
    def status_display(self):
        """Human-readable label for execution status"""
        status_map = {
            0: _("CREATED"),
            1: _("EXECUTION PROGRESS"),
            2: _("PARTIALLY COMPLETED"),
            3: _("COMPLETED"),
            4: _("SCHEDULED")
        }
        return status_map.get(self.status, _("UNKNOWN"))

    def __str__(self):
        if self.test_selection_type == 1 and self.test_suite:
            return f"{self.test_suite} - {self.device_group or 'Individual'} - {self.name}"
        elif self.test_selection_type == 0:
            test_count = self.individual_test_cases.count() if self.pk else 0
            return f"Individual Tests ({test_count}) - {self.device_group or 'Individual'} - {self.name}"
        else:
            return f"{self.name}"

    @property
    def active_device_count(self):
        from ..swapper import load_model
        TestSuiteExecutionDevice = load_model("TestSuiteExecutionDevice")

        return TestSuiteExecutionDevice.objects.filter(
            test_suite_execution=self,
            device__is_deleted=False
        ).count()


class AbstractScheduledExecution(models.Model):

    class Status(models.IntegerChoices):
        PENDING = 0, _('Pending')
        QUEUED = 1, _('Queued')  
        IN_PROCESS = 2, _('In Process')
        COMPLETED = 3, _('Completed')
        FAILED = 4, _('Failed')
        CANCELLED = 5, _('Cancelled')

    execution = models.ForeignKey(
        'test_management.TestSuiteExecution', 
        on_delete=models.CASCADE, 
        related_name="scheduled_executions"
    )
    scheduled_time = models.DateTimeField()
    status = models.IntegerField(
        choices=Status.choices,
        default=Status.PENDING
    )
    celery_task_id = models.CharField(max_length=255, blank=True, null=True)
    queued_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract= True
        ordering = ['scheduled_time']
        indexes = [
            models.Index(fields=['status', 'scheduled_time']),
            models.Index(fields=['celery_task_id']),
        ]

    def __str__(self):
        return f"{self.execution} @ {self.scheduled_time} ({self.status})"

    def is_due(self):
        """Check if this execution is due to run"""
        return (
            self.status == self.Status.PENDING and 
            self.scheduled_time <= timezone.now()
        )


class AbstractTestSuiteExecutionDevices(TimeStampedEditableModel):
    """
    Abstract model for Test Suite Execution Devices
    Links devices to test executions
    """
    test_suite_execution = models.ForeignKey(
        'test_management.TestSuiteExecution',
        on_delete=models.CASCADE,
        related_name='devices',
        verbose_name=_("test execution")
    )
    device = models.ForeignKey(
        'config.Device',
        on_delete=models.CASCADE,
        related_name='test_executions',
        verbose_name=_("device")
    )
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=[
            ('pending', _('Pending')),
            ('running', _('Running')),
            ('completed', _('Completed')),
            ('failed', _('Failed')),
        ],
        default='pending',
        help_text=_("Execution status on this device")
    )
    started_at = models.DateTimeField(
        _("started at"),
        null=True,
        blank=True,
        help_text=_("When execution started on this device")
    )
    completed_at = models.DateTimeField(
        _("completed at"),
        null=True,
        blank=True,
        help_text=_("When execution completed on this device")
    )
    output = models.TextField(
        _("output"),
        blank=True,
        help_text=_("Execution output/logs")
    )
    
    class Meta:
        abstract = True
        verbose_name = _("Test Group Execution Device")
        verbose_name_plural = _("Test Group Execution Devices")
        unique_together = ("test_suite_execution", "device")
        ordering = ["test_suite_execution", "device"]
    
    def __str__(self):
        return f"{self.test_suite_execution} - {self.device.name}"
    

class AbstractTestSuiteExecutionDevice(TimeStampedEditableModel):
    """
    Abstract model for Test Suite Execution Devices
    Links devices to test executions
    """
    CONNECTION_PROTOCOL_CHOICES= (
        (0, _("MQTT")),
        (1,_("SSH"))
    )
    test_suite_execution = models.ForeignKey(
        'test_management.TestSuiteExecution',
        on_delete=models.CASCADE,
        related_name='devices',
        verbose_name=_("test Group execution")
    )
    device = models.ForeignKey(
        'config.Device',
        on_delete=models.CASCADE,
        related_name='test_executions',
        verbose_name=_("device")
    )
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=[
            ('pending', _('Pending')),
            ('running', _('Running')),
            ('completed', _('Completed')),
            ('failed', _('Failed')),
        ],
        default='pending',
        help_text=_("Execution status on this device")
    )
    started_at = models.DateTimeField(
        _("started at"),
        null=True,
        blank=True,
        help_text=_("When execution started on this device")
    )
    completed_at = models.DateTimeField(
        _("completed at"),
        null=True,
        blank=True,
        help_text=_("When execution completed on this device")
    )
    output = models.TextField(
        _("output"),
        blank=True,
        help_text=_("Execution output/logs")
    )
    allure_report_path = models.CharField(
        _("allure report path"),
        max_length=255,
        blank=True,
        help_text=_("Path to the Allure report HTML file for this device execution")
    ) 
    connection_protocol = models.IntegerField(
        _("Connection Protocol"),
        choices=CONNECTION_PROTOCOL_CHOICES,
        default=0,  # Default to Test Suite for backward compatibility
        help_text=_("connection protocol used by device to run testcases.")
    )
    
    class Meta:
        abstract = True
        verbose_name = _("Test Group Execution Device")
        verbose_name_plural = _("Test Group Execution Devices")
        unique_together = ("test_suite_execution", "device")
        ordering = ["test_suite_execution", "device"]
    
    def __str__(self):
        return f"{self.test_suite_execution} - {self.device.name}"
    
    # ADD THESE HELPER METHODS
    @property
    def has_report(self):
        """Check if Allure report exists for this execution"""
        return bool(self.allure_report_path)
    
    def get_report_filename(self):
        """Generate report filename"""
        if not self.pk:
            return None
        timestamp = self.created.strftime('%Y%m%d_%H%M%S')
        device_name = self.device.name.replace(' ', '_').replace('/', '_')
        suite_name = self.test_suite_execution.test_suite.name.replace(' ', '_').replace('/', '_')
        return f"allure_report_{suite_name}_{device_name}_{timestamp}.html"
    
    def set_report_path(self, filename):
        """Set the report path"""
        self.allure_report_path = f"allure_reports/{filename}"
        self.save(update_fields=['allure_report_path'])
    
    def get_report_url(self):
        """Get the full URL for the report"""
        from django.conf import settings
        if self.allure_report_path:
            return f"{settings.MEDIA_URL}{self.allure_report_path}"
        return None
    

class AbstractTestCaseExecution(TimeStampedEditableModel):
    """
    Abstract model for individual test case execution results
    Tracks execution of a single test case on a single device
    """
    
    test_suite_execution = models.ForeignKey(
        'test_management.TestSuiteExecution',
        on_delete=models.CASCADE,
        related_name='test_case_executions',
        verbose_name=_("test group execution"),
        help_text=_("The parent test group execution")
    )
    device = models.ForeignKey(
        'config.Device',
        on_delete=models.CASCADE,
        related_name='test_case_executions',
        verbose_name=_("device"),
        help_text=_("Device where this test case was executed")
    )
    test_case = models.ForeignKey(
        'test_management.TestCase',
        on_delete=models.CASCADE,
        related_name='executions',
        verbose_name=_("test case"),
        help_text=_("The test case that was executed")
    )
    started_at = models.DateTimeField(
        _("started at"),
        null=True,
        blank=True,
        help_text=_("When this test case execution started")
    )
    completed_at = models.DateTimeField(
        _("completed at"),
        null=True,
        blank=True,
        help_text=_("When this test case execution completed")
    )
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=TestExecutionStatus.choices,
        default=TestExecutionStatus.PENDING,
        db_index=True,
        help_text=_("Current execution status")
    )
    execution_order = models.PositiveIntegerField(
        _("execution order"),
        default=0,
        help_text=_("Order in which this test case should be executed within the suite")
    )
    process_id = models.IntegerField(
        _("Process ID"),
        null=True,
        blank=True,
        help_text=_("Process ID returned by executor server.")
    )
    exit_code = models.IntegerField(
        _("exit code"),
        null=True,
        blank=True,
        help_text=_("Exit code returned by the test execution")
    )
    stdout = models.TextField(
        _("standard output"),
        blank=True,
        help_text=_("Standard output from test execution")
    )
    stderr = models.TextField(
        _("standard error"),
        blank=True,
        help_text=_("Standard error output from test execution")
    )
    result_data = models.JSONField(
        _("result data"),
        default=dict,
        blank=True,
        help_text=_("Additional structured result data (JSON format)")
    )
    
    # Performance metrics
    execution_duration = models.DurationField(
        _("execution duration"),
        null=True,
        blank=True,
        help_text=_("Total time taken for test execution")
    )
    
    # Error handling
    error_message = models.TextField(
        _("error message"),
        blank=True,
        help_text=_("Error message if execution failed")
    )
    retry_count = models.PositiveIntegerField(
        _("retry count"),
        default=0,
        help_text=_("Number of times this test case execution was retried")
    )
    
    class Meta:
        abstract = True
        verbose_name = _("Test Case Execution")
        verbose_name_plural = _("Test Case Executions")
        unique_together = ("test_suite_execution", "device", "test_case")
        ordering = ["test_suite_execution", "device", "execution_order"]
        indexes = [
            models.Index(fields=["test_suite_execution", "device"]),
            models.Index(fields=["status", "started_at"]),
            models.Index(fields=["test_case", "status"]),
        ]

    def __str__(self):
        return f"{self.test_case.test_case_id} on {self.device.name} - {self.get_status_display()}"

    def clean(self):
        """Validate the test case execution"""
        super().clean()
        
        # Ensure test case belongs to the same group
        if (self.test_case and self.test_suite_execution and 
            self.test_case not in self.test_suite_execution.test_suite.test_cases.all()):
            raise ValidationError({
                "test_case": _(
                    "Test case must belong to the test group being executed"
                )
            })
        
        # Ensure device is part of the execution
        if (self.device and self.test_suite_execution and
            not self.test_suite_execution.devices.filter(device=self.device).exists()):
            raise ValidationError({
                "device": _(
                    "Device must be part of the test group execution"
                )
            })
        
        if self.started_at and self.completed_at and self.started_at > self.completed_at:
            raise ValidationError({
                "completed_at": _("Completion time cannot be before start time")
            })

    def save(self, *args, **kwargs):
        # Calculate duration if both timestamps are available
        if self.started_at and self.completed_at:
            self.execution_duration = self.completed_at - self.started_at
        
        super().save(*args, **kwargs)  

 
class AbstractTestDeviceGroup(OrgMixin, TimeStampedEditableModel):
    """
    Abstract model for Test Device Groups
    Groups devices for test execution purposes
    """
    name = models.CharField(
        _("Group Name"),
        max_length=100,
        db_index=True,
        help_text=_("Name for the test device group (3-100 characters)")
    )
    description = models.TextField(
        _("Description"),
        max_length=500,
        help_text=_("Description of this device group (max 500 characters)")
    )
    
    class Meta:
        abstract = True
        verbose_name = _("Test Device Group")
        verbose_name_plural = _("Test Device Groups")
        unique_together = ("name", "organization")
        ordering = ["organization", "name"]

    def __str__(self):
        return f"{self.organization.name} - {self.name}"

    def clean(self):
        """Validate the test device group"""
        super().clean()
        
        # Validate name length
        if self.name and (len(self.name) < 3 or len(self.name) > 100):
         raise ValidationError({
                  "name": _("Group name must be between 3 and 100 characters")
         })
        
        # Validate description length
        if self.description and len(self.description) > 500:
            raise ValidationError({
                "description": _("Description cannot exceed 500 characters")
            })
        
        # Check for duplicate names within organization
        if self.name and self.organization_id:
            qs = self.__class__.objects.filter(
                organization=self.organization,
                name__iexact=self.name
            ).exclude(pk=self.pk)
            
            if qs.exists():
                raise ValidationError({
                    "name": _("A test device group with this name already exists in this organization")
                })

    @property
    def device_count(self):
        """Return count of devices in this group"""
        return self.devices.filter(device__is_deleted=False).count()


class AbstractTestDeviceGroupDevice(TimeStampedEditableModel):
    """
    Abstract model for Test Device Group Devices
    Links devices to test device groups
    """
    group = models.ForeignKey(
        'test_management.TestDeviceGroup',
        on_delete=models.CASCADE,
        related_name='devices',
        verbose_name=_("Test Device Group")
    )
    device = models.ForeignKey(
        'config.Device',
        on_delete=models.CASCADE,
        related_name='test_device_groups',
        verbose_name=_("Device")
    )
    
    class Meta:
        abstract = True
        verbose_name = _("Test Device Group Device")
        verbose_name_plural = _("Test Device Group Devices")
        unique_together = ("group", "device")
        ordering = ["group", "device"]

    def __str__(self):
        return f"{self.group.name} - {self.device.name}"

    def clean(self):
        """Validate device group membership"""
        super().clean()
        
        if not self.group_id or not self.device_id:
            return
        
        # Ensure device belongs to same organization
        if self.device.organization_id != self.group.organization_id:
            raise ValidationError({
                "device": _("Device must belong to the same organization as the group")
            })
        
        # Check if already exists
        if self.pk is None:  # Only check on creation
            if self.__class__.objects.filter(group=self.group, device=self.device).exists():
                raise ValidationError({
                    "device": _("This device is already in the group")
                })
        
        # Check organization device limit
        if hasattr(self.group.organization, 'config_limits'):
            device_limit = self.group.organization.config_limits.device_limit
            if device_limit > 0:  # 0 means unlimited
                current_count = self.__class__.objects.filter(group=self.group).count()
                if self.pk is None and current_count >= device_limit:
                                        raise ValidationError({
                        "device": _(f"Organization device limit ({device_limit}) reached")
                    })
        

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def is_deletable(self):
       """Check if device group can be deleted - not deletable if part of any execution"""
       from ..swapper import load_model
       TestSuiteExecution = load_model("TestSuiteExecution")
       return not TestSuiteExecution.objects.filter(device_group=self).exists()


class AbstractExecutionArtifact(models.Model):
    """
    Abstract model to save configuration files for testcases over different devices of the execution.
    """
    
    execution= models.ForeignKey(
        "test_management.TestSuiteExecution",
        on_delete=models.CASCADE,
        related_name="artifacts"
    )
    device= models.ForeignKey(
        "config.Device",
        on_delete=models.CASCADE
    )
    testcase= models.ForeignKey(
        "test_management.TestCase",
        on_delete=models.CASCADE
    )
    config_file= models.FileField(upload_to="execution_artifacts/")
    is_pushed= models.BooleanField(default=False)

    class Meta:
        abstract = True
        constraints= [
            models.UniqueConstraint(
                fields=["execution", "device", "testcase"],
                name="uniq_execution_device_testcase"
            )
        ]

    def clean(self):
        if self.pk:
            old = self.__class__.objects.get(pk=self.pk)
            if old.is_pushed and old.config_file != self.config_file:
                raise ValidationError(
                    "Configuration file cannot be modified after it has been pushed."
                )


class AbstractExecutionEmailLog(TimeStampedEditableModel):
    """
    Tracks individual email send status for each recipient per execution
    """
    class EmailStatus(models.IntegerChoices):
        PENDING = 0, _('Pending')
        QUEUED = 1, _('Queued')
        SENT = 2, _('Sent')
        FAILED = 3, _('Failed')
        RETRY = 4, _('Retry')

    execution = models.ForeignKey(
        'test_management.TestSuiteExecution',
        on_delete=models.CASCADE,
        related_name='email_logs',
        verbose_name=_("Test Execution")
    )
    email_address = models.EmailField(
        _("Email Address"),
        db_index=True
    )
    status = models.IntegerField(
        _("Status"),
        choices=EmailStatus.choices,
        default=EmailStatus.PENDING
    )
    celery_task_id = models.CharField(
        _("Celery Task ID"),
        max_length=255,
        blank=True,
        null=True
    )
    attempt_count = models.PositiveIntegerField(
        _("Attempt Count"),
        default=0
    )
    last_attempt_at = models.DateTimeField(
        _("Last Attempt At"),
        null=True,
        blank=True
    )
    sent_at = models.DateTimeField(
        _("Sent At"),
        null=True,
        blank=True
    )
    error_message = models.TextField(
        _("Error Message"),
        blank=True
    )

    class Meta:
        abstract = True
        verbose_name = _("Execution Email Log")
        verbose_name_plural = _("Execution Email Logs")
        unique_together = ("execution", "email_address")
        indexes = [
            models.Index(fields=["execution", "status"]),
            models.Index(fields=["status", "last_attempt_at"]),
        ]

    def __str__(self):
        return f"{self.execution.name} -> {self.email_address} ({self.get_status_display()})"