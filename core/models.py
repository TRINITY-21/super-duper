import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import FileExtensionValidator

class Supplier(AbstractUser):
    """Supplier model extending Django's User model"""
    supplier_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone = models.CharField(max_length=50, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    registration_number = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(
        max_length=50,
        choices=[
            ('active', 'Active'),
            ('suspended', 'Suspended'),
            ('inactive', 'Inactive')
        ],
        default='active'
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'suppliers'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.username} - {self.email}"


class Product(models.Model):
    """Product model for supplier submissions"""
    SUBMISSION_STATUSES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('in_review', 'In Review'),
        ('testing', 'Testing'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
    ]

    product_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.CASCADE,
        related_name='products',
        db_column='supplier_id'
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    category = models.CharField(max_length=100)
    sku = models.CharField(max_length=100, blank=True, null=True, unique=True)
    submission_status = models.CharField(
        max_length=50,
        choices=SUBMISSION_STATUSES,
        default='draft'
    )
    submission_date = models.DateTimeField(null=True, blank=True)
    review_date = models.DateTimeField(null=True, blank=True)
    completion_date = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    version = models.IntegerField(default=1)

    class Meta:
        db_table = 'products'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['supplier', 'submission_status']),
            models.Index(fields=['category']),
            models.Index(fields=['submission_date']),
        ]

    def __str__(self):
        return f"{self.name} - {self.category}"

    @property
    def tests_count(self):
        return self.tests.count()

    @property
    def tests_completed(self): 
        return self.tests.filter(status='completed').count()

    @property
    def tests_progress(self):
        if self.tests_count == 0:
            return "0%"
        return f"{round((self.tests_completed / self.tests_count) * 100)}%"


class ProductFile(models.Model):
    """Product file uploads (PDF, CSV, XML)"""
    FILE_TYPES = [
        ('PDF', 'PDF'),
        ('CSV', 'CSV'),
        ('XML', 'XML'),
        ('XLSX', 'Excel'),
        ('JSON', 'JSON'),
    ]

    UPLOAD_STATUSES = [
        ('pending', 'Pending'),
        ('uploaded', 'Uploaded'),
        ('validated', 'Validated'),
        ('failed', 'Failed'),
    ]

    file_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='files',
        db_column='product_id'
    )
    file = models.FileField(
        upload_to='product_files/%Y/%m/%d/',
        validators=[FileExtensionValidator(['pdf', 'csv', 'xml', 'xlsx', 'json'])]
    )
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=50, choices=FILE_TYPES)
    file_size = models.BigIntegerField()
    s3_bucket = models.CharField(max_length=255, blank=True, null=True)
    s3_key = models.CharField(max_length=1024, blank=True, null=True)
    file_hash = models.CharField(max_length=256, blank=True, null=True)
    upload_status = models.CharField(
        max_length=50,
        choices=UPLOAD_STATUSES,
        default='pending'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    validated_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'product_files'
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.file_name} - {self.product.name}"


class Test(models.Model):
    """Test model for multiple tests per product"""
    TEST_TYPES = [
        ('Safety', 'Safety'),
        ('Compliance', 'Compliance'),
        ('Quality', 'Quality'),
        ('Performance', 'Performance'),
        ('Environmental', 'Environmental'),
    ]

    TEST_STATUSES = [
        ('pending', 'Pending'),
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    RESULT_STATUSES = [
        ('pass', 'Pass'),
        ('fail', 'Fail'),
        ('conditional', 'Conditional'),
        ('pending', 'Pending'),
    ]

    PRIORITIES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    test_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='tests',
        db_column='product_id'
    )
    test_type = models.CharField(max_length=100, choices=TEST_TYPES)
    test_name = models.CharField(max_length=255)
    status = models.CharField(max_length=50, choices=TEST_STATUSES, default='pending')
    priority = models.CharField(max_length=20, choices=PRIORITIES, default='medium')
    assigned_to = models.CharField(max_length=255, blank=True, null=True)
    scheduled_date = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    result_summary = models.TextField(blank=True, null=True)
    result_status = models.CharField(
        max_length=50,
        choices=RESULT_STATUSES,
        blank=True,
        null=True
    )
    result_file_url = models.URLField(max_length=1024, blank=True, null=True)
    result_data = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tests'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product', 'status']),
            models.Index(fields=['test_type']),
            models.Index(fields=['assigned_to']),
            models.Index(fields=['scheduled_date']),
        ]

    def __str__(self):
        return f"{self.test_name} - {self.product.name}"


class TestHistory(models.Model):
    """Audit trail for test changes"""
    history_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    test = models.ForeignKey(
        Test,
        on_delete=models.CASCADE,
        related_name='history',
        db_column='test_id'
    )
    changed_by = models.CharField(max_length=255)
    change_type = models.CharField(max_length=50)
    old_status = models.CharField(max_length=50, blank=True, null=True)
    new_status = models.CharField(max_length=50, blank=True, null=True)
    change_description = models.TextField(blank=True, null=True)
    changed_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'test_history'
        ordering = ['-changed_at']

    def __str__(self):
        return f"{self.change_type} - {self.test.test_name}"


class Report(models.Model):
    """Report generation and storage"""
    REPORT_TYPES = [
        ('composite', 'Composite'),
        ('interim', 'Interim'),
        ('final', 'Final'),
        ('summary', 'Summary'),
    ]

    REPORT_FORMATS = [
        ('PDF', 'PDF'),
        ('JSON', 'JSON'),
        ('XML', 'XML'),
    ]

    REPORT_STATUSES = [
        ('pending', 'Pending'),
        ('generating', 'Generating'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    report_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='reports',
        db_column='product_id'
    )
    report_type = models.CharField(max_length=50, choices=REPORT_TYPES)
    report_format = models.CharField(max_length=20, choices=REPORT_FORMATS, default='PDF')
    report_url = models.URLField(max_length=1024, blank=True, null=True)
    s3_bucket = models.CharField(max_length=255, blank=True, null=True)
    s3_key = models.CharField(max_length=1024, blank=True, null=True)
    status = models.CharField(max_length=50, choices=REPORT_STATUSES, default='pending')
    generated_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    file_size = models.BigIntegerField(null=True, blank=True)
    checksum = models.CharField(max_length=256, blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'reports'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product', 'report_type']),
            models.Index(fields=['status']),
            models.Index(fields=['generated_at']),
        ]

    def __str__(self):
        return f"{self.report_type} - {self.product.name}"


class Notification(models.Model):
    """Notification system"""
    RECIPIENT_TYPES = [
        ('supplier', 'Supplier'),
        ('tester', 'Tester'),
        ('admin', 'Admin'),
    ]

    NOTIFICATION_STATUSES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('read', 'Read'),
    ]

    notification_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient_id = models.UUIDField()
    recipient_type = models.CharField(max_length=50, choices=RECIPIENT_TYPES)
    notification_type = models.CharField(max_length=50)
    subject = models.CharField(max_length=255)
    message = models.TextField()
    status = models.CharField(max_length=50, choices=NOTIFICATION_STATUSES, default='pending')
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient_id', 'recipient_type']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.subject} - {self.recipient_type}"


class AuditLog(models.Model):
    """System-wide audit logging"""
    log_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.CharField(max_length=255)
    user_type = models.CharField(max_length=50)
    action = models.CharField(max_length=100)
    entity_type = models.CharField(max_length=50)
    entity_id = models.UUIDField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    request_data = models.JSONField(default=dict, blank=True)
    response_status = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'audit_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user_id']),
            models.Index(fields=['entity_type', 'entity_id']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.action} - {self.entity_type}"
        