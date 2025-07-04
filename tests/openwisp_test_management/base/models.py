import logging
from django.utils import timezone


from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from openwisp_utils.base import TimeStampedEditableModel

logger = logging.getLogger(__name__)

# ADD THIS NEW ENUM CLASS HERE
class TestTypeChoices(models.IntegerChoices):
    ROBOT_FRAMEWORK = 1, _('Robot Framework')
    AGENT = 2, _('Agent')

class TestExecutionStatus(models.TextChoices):
    PENDING = 'pending', _('Pending')
    RUNNING = 'running', _('Running')
    SUCCESS = 'success', _('Success')
    FAILED = 'failed', _('Failed')
    TIMEOUT = 'timeout', _('Timeout')
    CANCELLED = 'cancelled', _('Cancelled')


class AbstractTestCategory(TimeStampedEditableModel):
    """
    Abstract model for Test Categories
    Categories group test cases by type or purpose
    """
    name = models.CharField(
        _("name"),
        max_length=64,
        db_index=True,
        unique=True,
        help_text=_("Category name to group related test cases")
    )
    code = models.CharField(
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
        ordering = ["name"]

    def __str__(self):
        return self.name

    def clean(self):
        """Validate the test category"""
        super().clean()
        if not self.name:
            raise ValidationError({"name": _("Name is required")})
        
        # Check for duplicate names
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
    def test_suite_count(self):
        """Return count of test suites in this category"""
        from ..swapper import load_model
        TestSuite = load_model("TestSuite")
        return TestSuite.objects.filter(category=self).count()

    @property
    def is_deletable(self):
        """Check if category can be deleted"""
        # Categories with test cases or test suites cannot be deleted
        return self.test_case_count == 0 and self.test_suite_count == 0


class AbstractTestCase(TimeStampedEditableModel):
    """
    Abstract model for Test Cases
    Individual test cases that can be executed on devices
    """
    name = models.CharField(
        _("test case name"),
        max_length=128,
        db_index=True,
        help_text=_("Descriptive name for the test case")
    )
    test_case_id = models.CharField(
        _("test case ID"),
        max_length=64,
        unique=True,
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
    test_type = models.IntegerField(
        _("test type"),
        choices=TestTypeChoices.choices,
        default=TestTypeChoices.ROBOT_FRAMEWORK,
        help_text=_("Type of test: Robot Framework or Agent ")
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
        return f"{self.category.name} - {self.name} ({self.get_test_type_display()})"


    def clean(self):
        """Validate the test case"""
        super().clean()
        
        # Validate required fields
        if not self.name:
            raise ValidationError({"name": _("Test case name is required")})
        
        if not self.test_case_id:
            raise ValidationError({"test_case_id": _("Test case ID is required")})
        
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
    def suite_count(self):
        """Return count of test suites containing this test case"""
        from ..swapper import load_model
        TestSuiteCase = load_model("TestSuiteCase")
        return TestSuiteCase.objects.filter(test_case=self).count()

    @property
    def execution_count(self):
        """Return count of times this test has been executed"""
        # This will be implemented when TestExecution model is added
        return 0

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
        _("name"),
        max_length=128,
        db_index=True,
        help_text=_("Descriptive name for the test suite")
    )
    description = models.TextField(
        _("description"),
        blank=True,
        help_text=_("Detailed description of what this test suite does")
    )
    is_active = models.BooleanField(
        _("is active"),
        default=True,
        help_text=_("Whether this test suite is currently active")
    )
    category = models.ForeignKey(
        'test_management.TestCategory',
        on_delete=models.PROTECT,
        related_name='test_suites',
        verbose_name=_("category"),
        help_text=_("Category this test suite belongs to")
    )
    test_cases = models.ManyToManyField(
        'test_management.TestCase',
        through='test_management.TestSuiteCase',
        related_name='test_suites',
        verbose_name=_("test cases"),
        help_text=_("Test cases included in this suite")
    )

    class Meta:
        abstract = True
        verbose_name = _("Test Suite")
        verbose_name_plural = _("Test Suites")
        unique_together = ("category", "name")
        ordering = ["category", "name"]

    def __str__(self):
        return f"{self.category.name} - {self.name}"

    def clean(self):
        """Validate the test suite"""
        super().clean()
        
        if not self.name:
            raise ValidationError({"name": _("Name is required")})
        
        # Check for duplicate name within the same category
        if self.category_id:
            qs = self.__class__.objects.filter(
                category=self.category,
                name__iexact=self.name
            ).exclude(pk=self.pk)
            
            if qs.exists():
                raise ValidationError({
                    "name": _(
                        f"A test suite with this name already exists "
                        f"in category '{self.category.name}'"
                    )
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def test_case_count(self):
        """Return count of test cases in this suite"""
        return self.test_cases.count()

    @property
    def execution_count(self):
        """Return count of times this suite has been executed"""
        # This will be implemented when MassExecution model is added
        return 0

    @property
    def is_deletable(self):
        """Check if test suite can be deleted"""
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
        on_delete=models.CASCADE,
        verbose_name=_("test suite")
    )
    test_case = models.ForeignKey(
        'test_management.TestCase',
        on_delete=models.CASCADE,
        verbose_name=_("test case")
    )
    order = models.PositiveIntegerField(
        _("order"),
        default=0,
        help_text=_("Execution order of test case within the suite")
    )

    class Meta:
        abstract = True
        verbose_name = _("Test Suite Case")
        verbose_name_plural = _("Test Suite Cases")
        unique_together = ("test_suite", "test_case")
        ordering = ["test_suite", "order", "test_case"]

    def __str__(self):
        return f"{self.test_suite.name} - {self.order}: {self.test_case.name}"

    def clean(self):
        """Validate test suite case"""
        super().clean()
        
        # Ensure test case belongs to the same category as the suite
        if self.test_case and self.test_suite:
            if self.test_case.category != self.test_suite.category:
                raise ValidationError({
                    "test_case": _(
                        "Test case must belong to the same category as the test suite"
                    )
                })

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
    test_suite = models.ForeignKey(
        'test_management.TestSuite',
        on_delete=models.PROTECT,
        related_name='executions',
        verbose_name=_("test suite"),
        help_text=_("Test suite to execute")
    )
    is_executed = models.BooleanField(
        _("is executed"),
        default=False,
        help_text=_("Whether the execution has completed")
    )
    
    class Meta:
        abstract = True
        verbose_name = _("Test Suite Execution")
        verbose_name_plural = _("Test Suite Executions")
        ordering = ["-created"]
    
    def __str__(self):
        return f"{self.test_suite.name} - {self.created.strftime('%Y-%m-%d %H:%M')}"
    
    @property
    def device_count(self):
        """Return count of devices in this execution"""
        from ..swapper import load_model
        TestSuiteExecutionDevice = load_model("TestSuiteExecutionDevice")
        return TestSuiteExecutionDevice.objects.filter(test_suite_execution=self).count()
    
    @property
    def status_summary(self):
     """Return summary of execution status"""
     from ..swapper import load_model
     TestSuiteExecutionDevice = load_model("TestSuiteExecutionDevice")
    
     devices = TestSuiteExecutionDevice.objects.filter(test_suite_execution=self)
     total = devices.count()
    
    # Always return a dictionary, not a string
     if total == 0:
        return {
            'total': 0,
            'completed': 0,
            'failed': 0,
            'pending': 0,
            'running': 0,
            'has_devices': False
        }
    
     completed = devices.filter(status='completed').count()
     failed = devices.filter(status='failed').count()
     pending = devices.filter(status='pending').count()
     running = devices.filter(status='running').count()
    
     return {
        'total': total,
        'completed': completed,
        'failed': failed,
        'pending': pending,
        'running': running,
        'has_devices': True
    }

@property
def execution_time(self):
    """Calculate total execution time"""
    from ..swapper import load_model
    TestSuiteExecutionDevice = load_model("TestSuiteExecutionDevice")
    
    devices = TestSuiteExecutionDevice.objects.filter(
        test_suite_execution=self
    ).exclude(
        started_at__isnull=True
    )
    
    if not devices.exists():
        return None
    
    # Get earliest start time and latest completion time
    start_time = devices.aggregate(
        min_start=models.Min('started_at')
    )['min_start']
    
    end_time = devices.filter(
        completed_at__isnull=False
    ).aggregate(
        max_end=models.Max('completed_at')
    )['max_end']
    
    if start_time and end_time:
        duration = end_time - start_time
        return duration
    
    return None


class AbstractTestSuiteExecutionDevice(TimeStampedEditableModel):
    """
    Abstract model for Test Suite Execution Devices
    Links devices to test suite executions
    """
    test_suite_execution = models.ForeignKey(
        'test_management.TestSuiteExecution',
        on_delete=models.CASCADE,
        related_name='devices',
        verbose_name=_("test suite execution")
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
        verbose_name = _("Test Suite Execution Device")
        verbose_name_plural = _("Test Suite Execution Devices")
        unique_together = ("test_suite_execution", "device")
        ordering = ["test_suite_execution", "device"]
    
    def __str__(self):
        return f"{self.test_suite_execution} - {self.device.name}"
    


class AbstractTestCaseExecution(TimeStampedEditableModel):
    """
    Abstract model for individual test case execution results
    Tracks execution of a single test case on a single device
    """
    test_suite_execution = models.ForeignKey(
        'test_management.TestSuiteExecution',
        on_delete=models.CASCADE,
        related_name='test_case_executions',
        verbose_name=_("test suite execution"),
        help_text=_("The parent test suite execution")
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
    
    # Execution timing
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
    
    # Execution status and results
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=TestExecutionStatus.choices,
        default=TestExecutionStatus.PENDING,
        db_index=True,
        help_text=_("Current execution status")
    )
    
    # Execution order within the suite
    execution_order = models.PositiveIntegerField(
        _("execution order"),
        default=0,
        help_text=_("Order in which this test case should be executed within the suite")
    )
    
    # Results and output
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
        
        # Ensure test case belongs to the same suite
        if (self.test_case and self.test_suite_execution and 
            self.test_case not in self.test_suite_execution.test_suite.test_cases.all()):
            raise ValidationError({
                "test_case": _(
                    "Test case must belong to the test suite being executed"
                )
            })
        
        # Ensure device is part of the execution
        if (self.device and self.test_suite_execution and
            not self.test_suite_execution.devices.filter(device=self.device).exists()):
            raise ValidationError({
                "device": _(
                    "Device must be part of the test suite execution"
                )
            })
        
        # Validate timing
        if self.started_at and self.completed_at and self.started_at > self.completed_at:
            raise ValidationError({
                "completed_at": _("Completion time cannot be before start time")
            })

    def save(self, *args, **kwargs):
        # Calculate duration if both timestamps are available
        if self.started_at and self.completed_at:
            self.execution_duration = self.completed_at - self.started_at
        
        # Set execution order from TestSuiteCase if not set
        if self.execution_order == 0 and self.test_case and self.test_suite_execution:
            try:
                suite_case = TestSuiteCase.objects.get(
                    test_suite=self.test_suite_execution.test_suite,
                    test_case=self.test_case
                )
                self.execution_order = suite_case.order
            except TestSuiteCase.DoesNotExist:
                pass
        
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def is_completed(self):
        """Check if execution is completed (success or failed)"""
        return self.status in [
            TestExecutionStatus.SUCCESS,
            TestExecutionStatus.FAILED,
            TestExecutionStatus.TIMEOUT,
            TestExecutionStatus.CANCELLED
        ]

    @property
    def is_successful(self):
        """Check if execution was successful"""
        return self.status == TestExecutionStatus.SUCCESS

    @property
    def duration_seconds(self):
        """Return duration in seconds"""
        if self.execution_duration:
            return self.execution_duration.total_seconds()
        return None

    @property
    def formatted_duration(self):
        """Return human-readable duration"""
        if self.execution_duration:
            total_seconds = int(self.execution_duration.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            if hours > 0:
                return f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                return f"{minutes}m {seconds}s"
            else:
                return f"{seconds}s"
        return None

    def start_execution(self):
        """Mark execution as started"""
        self.status = TestExecutionStatus.RUNNING
        self.started_at = timezone.now()
        self.save(update_fields=['status', 'started_at'])

    def complete_execution(self, success=True, exit_code=None, stdout="", stderr="", error_message=""):
        """Mark execution as completed"""
        self.status = TestExecutionStatus.SUCCESS if success else TestExecutionStatus.FAILED
        self.completed_at = timezone.now()
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.error_message = error_message
        
        if self.started_at:
            self.execution_duration = self.completed_at - self.started_at
        
        self.save(update_fields=[
            'status', 'completed_at', 'exit_code', 'stdout', 
            'stderr', 'error_message', 'execution_duration'
        ])

    def fail_execution(self, error_message, exit_code=None, stderr=""):
        """Mark execution as failed"""
        self.complete_execution(
            success=False,
            exit_code=exit_code,
            stderr=stderr,
            error_message=error_message
        )

    def timeout_execution(self, timeout_message="Execution timed out"):
        """Mark execution as timed out"""
        self.status = TestExecutionStatus.TIMEOUT
        self.completed_at = timezone.now()
        self.error_message = timeout_message
        
        if self.started_at:
            self.execution_duration = self.completed_at - self.started_at
        
        self.save(update_fields=[
            'status', 'completed_at', 'error_message', 'execution_duration'
        ])

    def cancel_execution(self, cancel_message="Execution cancelled"):
        """Mark execution as cancelled"""
        self.status = TestExecutionStatus.CANCELLED
        self.completed_at = timezone.now()
        self.error_message = cancel_message
        
        if self.started_at:
            self.execution_duration = self.completed_at - self.started_at
        
        self.save(update_fields=[
            'status', 'completed_at', 'error_message', 'execution_duration'
        ])
