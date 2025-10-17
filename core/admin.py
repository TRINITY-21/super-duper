from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    Supplier, Product, ProductFile, Test, 
    TestHistory, Report, Notification, AuditLog
)


@admin.register(Supplier)
class SupplierAdmin(UserAdmin):
    """Enhanced Supplier admin with custom fields"""
    list_display = [
        'username', 'email', 'first_name', 'last_name', 
        'phone', 'status_badge', 'product_count', 'created_at'
    ]
    list_filter = ['status', 'is_staff', 'is_active', 'created_at']
    search_fields = ['username', 'email', 'first_name', 'last_name', 'phone', 'registration_number']
    ordering = ['-created_at']
    
    # Add custom fields to the user admin form
    fieldsets = UserAdmin.fieldsets + (
        ('Supplier Information', {
            'fields': ('phone', 'address', 'registration_number', 'status', 'metadata')
        }),
    )
    
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Supplier Information', {
            'fields': ('phone', 'address', 'registration_number', 'status')
        }),
    )
    
    def status_badge(self, obj):
        """Display status as a colored badge"""
        colors = {
            'active': 'green',
            'suspended': 'orange',
            'inactive': 'red'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            colors.get(obj.status, 'gray'),
            obj.status.upper()
        )
    status_badge.short_description = 'Status'
    
    def product_count(self, obj):
        """Display number of products"""
        count = obj.products.count()
        url = reverse('admin:core_product_changelist') + f'?supplier__id__exact={obj.supplier_id}'
        return format_html('<a href="{}">{} products</a>', url, count)
    product_count.short_description = 'Products'


class ProductFileInline(admin.TabularInline):
    """Inline for product files"""
    model = ProductFile
    extra = 0
    fields = ['file_name', 'file_type', 'file_size_display', 'upload_status', 'uploaded_at']
    readonly_fields = ['file_size_display', 'uploaded_at']
    
    def file_size_display(self, obj):
        """Display file size in human-readable format"""
        if obj.file_size:
            size_mb = obj.file_size / (1024 * 1024)
            return f"{size_mb:.2f} MB"
        return "-"
    file_size_display.short_description = 'File Size'


class TestInline(admin.TabularInline):
    """Inline for tests"""
    model = Test
    extra = 0
    fields = ['test_name', 'test_type', 'status', 'result_status', 'priority', 'completed_at']
    readonly_fields = ['completed_at']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('product')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """Enhanced Product admin"""
    list_display = [
        'name', 'supplier_link', 'category', 'sku', 
        'submission_status_badge', 'tests_summary', 'submission_date', 'created_at'
    ]
    list_filter = ['submission_status', 'category', 'created_at', 'submission_date']
    search_fields = ['name', 'sku', 'category', 'supplier__username', 'supplier__email']
    readonly_fields = ['product_id', 'created_at', 'updated_at', 'tests_progress_bar']
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('product_id', 'supplier', 'name', 'description', 'category', 'sku')
        }),
        ('Status', {
            'fields': ('submission_status', 'submission_date', 'review_date', 'completion_date')
        }),
        ('Progress', {
            'fields': ('tests_progress_bar',)
        }),
        ('Metadata', {
            'fields': ('metadata', 'version'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [ProductFileInline, TestInline]
    
    def supplier_link(self, obj):
        """Link to supplier"""
        url = reverse('admin:core_supplier_change', args=[obj.supplier.supplier_id])
        return format_html('<a href="{}">{}</a>', url, obj.supplier.username)
    supplier_link.short_description = 'Supplier'
    
    def submission_status_badge(self, obj):
        """Display submission status as colored badge"""
        colors = {
            'draft': 'gray',
            'submitted': 'blue',
            'in_review': 'orange',
            'testing': 'purple',
            'completed': 'green',
            'rejected': 'red'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            colors.get(obj.submission_status, 'gray'),
            obj.submission_status.replace('_', ' ').upper()
        )
    submission_status_badge.short_description = 'Status'
    
    def tests_summary(self, obj):
        """Display test summary"""
        total = obj.tests.count()
        completed = obj.tests.filter(status='completed').count()
        passed = obj.tests.filter(result_status='pass').count()
        
        if total == 0:
            return "No tests"
        
        return format_html(
            '<span title="{} passed">{}/{} completed</span>',
            passed, completed, total
        )
    tests_summary.short_description = 'Tests'
    
    def tests_progress_bar(self, obj):
        """Display visual progress bar for tests"""
        total = obj.tests.count()
        if total == 0:
            return "No tests scheduled"
        
        completed = obj.tests.filter(status='completed').count()
        passed = obj.tests.filter(result_status='pass').count()
        failed = obj.tests.filter(result_status='fail').count()
        
        percentage = (completed / total) * 100
        passed_percentage = (passed / total) * 100
        failed_percentage = (failed / total) * 100
        
        return format_html(
            '''
            <div style="width: 100%; background-color: #f0f0f0; border-radius: 5px; overflow: hidden;">
                <div style="width: {}%; background-color: #4CAF50; height: 20px; float: left;"></div>
                <div style="width: {}%; background-color: #f44336; height: 20px; float: left;"></div>
            </div>
            <small>{}/{} completed | {} passed | {} failed</small>
            ''',
            passed_percentage, failed_percentage,
            completed, total, passed, failed
        )
    tests_progress_bar.short_description = 'Test Progress'


@admin.register(ProductFile)
class ProductFileAdmin(admin.ModelAdmin):
    """Product File admin"""
    list_display = [
        'file_name', 'product_link', 'file_type', 
        'file_size_display', 'upload_status_badge', 'uploaded_at'
    ]
    list_filter = ['file_type', 'upload_status', 'uploaded_at']
    search_fields = ['file_name', 'product__name', 's3_key']
    readonly_fields = ['file_id', 'file_hash', 'uploaded_at', 'validated_at']
    ordering = ['-uploaded_at']
    date_hierarchy = 'uploaded_at'
    
    fieldsets = (
        ('File Information', {
            'fields': ('file_id', 'product', 'file', 'file_name', 'file_type', 'file_size')
        }),
        ('Storage', {
            'fields': ('s3_bucket', 's3_key', 'file_hash')
        }),
        ('Status', {
            'fields': ('upload_status', 'uploaded_at', 'validated_at')
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
    )
    
    def product_link(self, obj):
        """Link to product"""
        url = reverse('admin:core_product_change', args=[obj.product.product_id])
        return format_html('<a href="{}">{}</a>', url, obj.product.name)
    product_link.short_description = 'Product'
    
    def file_size_display(self, obj):
        """Display file size in MB"""
        if obj.file_size:
            size_mb = obj.file_size / (1024 * 1024)
            return f"{size_mb:.2f} MB"
        return "-"
    file_size_display.short_description = 'Size'
    
    def upload_status_badge(self, obj):
        """Display upload status as badge"""
        colors = {
            'pending': 'orange',
            'uploaded': 'blue',
            'validated': 'green',
            'failed': 'red'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            colors.get(obj.upload_status, 'gray'),
            obj.upload_status.upper()
        )
    upload_status_badge.short_description = 'Status'


class TestHistoryInline(admin.TabularInline):
    """Inline for test history"""
    model = TestHistory
    extra = 0
    fields = ['changed_by', 'change_type', 'old_status', 'new_status', 'changed_at']
    readonly_fields = ['changed_by', 'change_type', 'old_status', 'new_status', 'changed_at']
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    """Enhanced Test admin"""
    list_display = [
        'test_name', 'product_link', 'test_type_badge', 
        'status_badge', 'result_badge', 'priority_badge', 
        'assigned_to', 'scheduled_date', 'completed_at'
    ]
    list_filter = ['test_type', 'status', 'result_status', 'priority', 'scheduled_date']
    search_fields = ['test_name', 'product__name', 'assigned_to', 'notes']
    readonly_fields = ['test_id', 'created_at', 'updated_at']
    ordering = ['-created_at']
    date_hierarchy = 'scheduled_date'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('test_id', 'product', 'test_type', 'test_name', 'priority')
        }),
        ('Assignment', {
            'fields': ('assigned_to', 'scheduled_date')
        }),
        ('Status', {
            'fields': ('status', 'started_at', 'completed_at')
        }),
        ('Results', {
            'fields': ('result_status', 'result_summary', 'result_file_url', 'result_data')
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [TestHistoryInline]
    
    actions = ['mark_as_completed', 'mark_as_in_progress']
    
    def product_link(self, obj):
        """Link to product"""
        url = reverse('admin:core_product_change', args=[obj.product.product_id])
        return format_html('<a href="{}">{}</a>', url, obj.product.name)
    product_link.short_description = 'Product'
    
    def test_type_badge(self, obj):
        """Display test type as badge"""
        colors = {
            'Safety': '#2196F3',
            'Compliance': '#4CAF50',
            'Quality': '#FF9800',
            'Performance': '#9C27B0',
            'Environmental': '#009688'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            colors.get(obj.test_type, 'gray'),
            obj.test_type
        )
    test_type_badge.short_description = 'Type'
    
    def status_badge(self, obj):
        """Display status as badge"""
        colors = {
            'pending': 'gray',
            'scheduled': 'blue',
            'in_progress': 'orange',
            'completed': 'green',
            'failed': 'red',
            'cancelled': 'darkgray'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            colors.get(obj.status, 'gray'),
            obj.status.replace('_', ' ').upper()
        )
    status_badge.short_description = 'Status'
    
    def result_badge(self, obj):
        """Display result as badge"""
        if not obj.result_status:
            return '-'
        
        colors = {
            'pass': 'green',
            'fail': 'red',
            'conditional': 'orange',
            'pending': 'gray'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            colors.get(obj.result_status, 'gray'),
            obj.result_status.upper()
        )
    result_badge.short_description = 'Result'
    
    def priority_badge(self, obj):
        """Display priority as badge"""
        colors = {
            'low': '#4CAF50',
            'medium': '#FF9800',
            'high': '#f44336',
            'urgent': '#9C27B0'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            colors.get(obj.priority, 'gray'),
            obj.priority.upper()
        )
    priority_badge.short_description = 'Priority'
    
    def mark_as_completed(self, request, queryset):
        """Bulk action to mark tests as completed"""
        updated = queryset.update(status='completed')
        self.message_user(request, f'{updated} tests marked as completed.')
    mark_as_completed.short_description = 'Mark selected as completed'
    
    def mark_as_in_progress(self, request, queryset):
        """Bulk action to mark tests as in progress"""
        updated = queryset.update(status='in_progress')
        self.message_user(request, f'{updated} tests marked as in progress.')
    mark_as_in_progress.short_description = 'Mark selected as in progress'


@admin.register(TestHistory)
class TestHistoryAdmin(admin.ModelAdmin):
    """Test History admin"""
    list_display = [
        'test_link', 'change_type', 'old_status', 'new_status', 
        'changed_by', 'changed_at'
    ]
    list_filter = ['change_type', 'changed_at']
    search_fields = ['test__test_name', 'changed_by', 'change_description']
    readonly_fields = ['history_id', 'test', 'changed_by', 'change_type', 'old_status', 'new_status', 'changed_at']
    ordering = ['-changed_at']
    date_hierarchy = 'changed_at'
    
    def test_link(self, obj):
        """Link to test"""
        url = reverse('admin:core_test_change', args=[obj.test.test_id])
        return format_html('<a href="{}">{}</a>', url, obj.test.test_name)
    test_link.short_description = 'Test'
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    """Report admin"""
    list_display = [
        'report_id_short', 'product_link', 'report_type_badge', 
        'report_format', 'status_badge', 'file_size_display', 'generated_at'
    ]
    list_filter = ['report_type', 'report_format', 'status', 'generated_at']
    search_fields = ['report_id', 'product__name']
    readonly_fields = ['report_id', 'generated_at', 'created_at', 'download_link']
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Report Information', {
            'fields': ('report_id', 'product', 'report_type', 'report_format')
        }),
        ('Status', {
            'fields': ('status', 'generated_at', 'expires_at')
        }),
        ('Storage', {
            'fields': ('report_url', 'download_link', 's3_bucket', 's3_key', 'file_size', 'checksum')
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def report_id_short(self, obj):
        """Display shortened report ID"""
        return str(obj.report_id)[:8] + '...'
    report_id_short.short_description = 'Report ID'
    
    def product_link(self, obj):
        """Link to product"""
        url = reverse('admin:core_product_change', args=[obj.product.product_id])
        return format_html('<a href="{}">{}</a>', url, obj.product.name)
    product_link.short_description = 'Product'
    
    def report_type_badge(self, obj):
        """Display report type as badge"""
        colors = {
            'composite': '#2196F3',
            'interim': '#FF9800',
            'final': '#4CAF50',
            'summary': '#9C27B0'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            colors.get(obj.report_type, 'gray'),
            obj.report_type.upper()
        )
    report_type_badge.short_description = 'Type'
    
    def status_badge(self, obj):
        """Display status as badge"""
        colors = {
            'pending': 'gray',
            'generating': 'orange',
            'completed': 'green',
            'failed': 'red'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            colors.get(obj.status, 'gray'),
            obj.status.upper()
        )
    status_badge.short_description = 'Status'
    
    def file_size_display(self, obj):
        """Display file size in MB"""
        if obj.file_size:
            size_mb = obj.file_size / (1024 * 1024)
            return f"{size_mb:.2f} MB"
        return "-"
    file_size_display.short_description = 'Size'
    
    def download_link(self, obj):
        """Display download link if available"""
        if obj.status == 'completed' and obj.report_url:
            return format_html('<a href="{}" target="_blank">Download Report</a>', obj.report_url)
        return "Not available"
    download_link.short_description = 'Download'


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Notification admin"""
    list_display = [
        'subject', 'recipient_type', 'notification_type', 
        'status_badge', 'sent_at', 'read_at'
    ]
    list_filter = ['recipient_type', 'notification_type', 'status', 'sent_at']
    search_fields = ['subject', 'message', 'recipient_id']
    readonly_fields = ['notification_id', 'created_at', 'sent_at', 'read_at']
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Notification Information', {
            'fields': ('notification_id', 'recipient_id', 'recipient_type', 'notification_type')
        }),
        ('Content', {
            'fields': ('subject', 'message')
        }),
        ('Status', {
            'fields': ('status', 'sent_at', 'read_at')
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def status_badge(self, obj):
        """Display status as badge"""
        colors = {
            'pending': 'gray',
            'sent': 'green',
            'failed': 'red',
            'read': 'blue'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            colors.get(obj.status, 'gray'),
            obj.status.upper()
        )
    status_badge.short_description = 'Status'


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Audit Log admin (read-only)"""
    list_display = [
        'user_id', 'user_type', 'action', 'entity_type', 
        'entity_id_short', 'response_status', 'ip_address', 'created_at'
    ]
    list_filter = ['user_type', 'action', 'entity_type', 'response_status', 'created_at']
    search_fields = ['user_id', 'action', 'entity_type', 'entity_id', 'ip_address']
    readonly_fields = [
        'log_id', 'user_id', 'user_type', 'action', 'entity_type', 
        'entity_id', 'ip_address', 'user_agent', 'request_data', 
        'response_status', 'created_at'
    ]
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    
    def entity_id_short(self, obj):
        """Display shortened entity ID"""
        if obj.entity_id:
            return str(obj.entity_id)[:8] + '...'
        return '-'
    entity_id_short.short_description = 'Entity ID'
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


admin.site.site_header = "Testing Platform Administration"
admin.site.site_title = "Testing Platform Admin"
admin.site.index_title = "Welcome to Testing Platform Admin Portal"