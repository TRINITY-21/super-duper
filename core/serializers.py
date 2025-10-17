from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import (
    Supplier, Product, ProductFile, Test, 
    TestHistory, Report, Notification, AuditLog
)


class SupplierRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for supplier registration"""
    password = serializers.CharField(
        write_only=True, 
        required=True, 
        validators=[validate_password]
    )
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = Supplier
        fields = [
            'supplier_id', 'username', 'email', 'password', 'password2',
            'first_name', 'last_name', 'phone', 'address', 
            'registration_number', 'created_at'
        ]
        read_only_fields = ['supplier_id', 'created_at']

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError(
                {"password": "Password fields didn't match."}
            )
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')
        user = Supplier.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            phone=validated_data.get('phone', ''),
            address=validated_data.get('address', ''),
            registration_number=validated_data.get('registration_number', ''),
        )
        return user


class SupplierSerializer(serializers.ModelSerializer):
    """Serializer for supplier details"""
    total_products = serializers.SerializerMethodField()

    class Meta:
        model = Supplier
        fields = [
            'supplier_id', 'username', 'email', 'first_name', 'last_name',
            'phone', 'address', 'status', 'total_products', 'created_at'
        ]
        read_only_fields = ['supplier_id', 'created_at']

    def get_total_products(self, obj):
        return obj.products.count()


class ProductFileSerializer(serializers.ModelSerializer):
    """Serializer for product files"""
    class Meta:
        model = ProductFile
        fields = [
            'file_id', 'product', 'file', 'file_name', 'file_type',
            'file_size', 'upload_status', 'uploaded_at', 's3_key'
        ]
        read_only_fields = ['file_id', 'uploaded_at', 'file_size', 's3_key']

    def validate_file(self, value):
        # Validate file size (100MB max)
        if value.size > 100 * 1024 * 1024:
            raise serializers.ValidationError("File size cannot exceed 100MB")
        return value


class ProductListSerializer(serializers.ModelSerializer):
    """Serializer for product list view"""
    tests_progress = serializers.ReadOnlyField()
    total_tests = serializers.SerializerMethodField()
    completed_tests = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'product_id', 'name', 'category', 'submission_status',
            'total_tests', 'completed_tests', 'tests_progress', 'created_at'
        ]

    def get_total_tests(self, obj):
        return obj.tests.count()

    def get_completed_tests(self, obj):
        return obj.tests.filter(status='completed').count()


class ProductDetailSerializer(serializers.ModelSerializer):
    """Serializer for product detail view"""
    files = ProductFileSerializer(many=True, read_only=True)
    tests_count = serializers.ReadOnlyField()
    tests_completed = serializers.ReadOnlyField()
    tests_progress = serializers.ReadOnlyField()
    supplier_name = serializers.CharField(source='supplier.username', read_only=True)

    class Meta:
        model = Product
        fields = [
            'product_id', 'supplier', 'supplier_name', 'name', 'description',
            'category', 'sku', 'submission_status', 'submission_date',
            'review_date', 'completion_date', 'metadata', 'files',
            'tests_count', 'tests_completed', 'tests_progress',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'product_id', 'submission_date', 'review_date', 
            'completion_date', 'created_at', 'updated_at'
        ]


class ProductCreateSerializer(serializers.ModelSerializer):
    """Serializer for product creation"""
    class Meta:
        model = Product
        fields = [
            'product_id', 'name', 'description', 'category', 
            'sku', 'metadata', 'created_at'
        ]
        read_only_fields = ['product_id', 'created_at']


class TestHistorySerializer(serializers.ModelSerializer):
    """Serializer for test history"""
    class Meta:
        model = TestHistory
        fields = [
            'history_id', 'test', 'changed_by', 'change_type',
            'old_status', 'new_status', 'change_description', 'changed_at'
        ]
        read_only_fields = ['history_id', 'changed_at']


class TestSerializer(serializers.ModelSerializer):
    """Serializer for test operations"""
    history = TestHistorySerializer(many=True, read_only=True)

    class Meta:
        model = Test
        fields = [
            'test_id', 'product', 'test_type', 'test_name', 'status',
            'priority', 'assigned_to', 'scheduled_date', 'started_at',
            'completed_at', 'result_summary', 'result_status',
            'result_file_url', 'result_data', 'notes', 'history',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['test_id', 'created_at', 'updated_at']

    def update(self, instance, validated_data):
        # Create history entry on status change
        if 'status' in validated_data and validated_data['status'] != instance.status:
            TestHistory.objects.create(
                test=instance,
                changed_by=self.context['request'].user.username,
                change_type='status_update',
                old_status=instance.status,
                new_status=validated_data['status']
            )
        return super().update(instance, validated_data)


class TestListSerializer(serializers.ModelSerializer):
    """Serializer for test list view"""
    class Meta:
        model = Test
        fields = [
            'test_id', 'test_type', 'test_name', 'status',
            'result_status', 'priority', 'scheduled_date', 'completed_at'
        ]


class ReportSerializer(serializers.ModelSerializer):
    """Serializer for report operations"""
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = Report
        fields = [
            'report_id', 'product', 'report_type', 'report_format',
            'status', 'generated_at', 'expires_at', 'file_size',
            'download_url', 'metadata', 'created_at'
        ]
        read_only_fields = [
            'report_id', 'status', 'generated_at', 
            'file_size', 'created_at'
        ]

    def get_download_url(self, obj):
        if obj.status == 'completed' and obj.report_url:
            return obj.report_url
        return None


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for notifications"""
    class Meta:
        model = Notification
        fields = [
            'notification_id', 'recipient_id', 'recipient_type',
            'notification_type', 'subject', 'message', 'status',
            'sent_at', 'read_at', 'created_at'
        ]
        read_only_fields = ['notification_id', 'sent_at', 'read_at', 'created_at']


class AuditLogSerializer(serializers.ModelSerializer):
    """Serializer for audit logs"""
    class Meta:
        model = AuditLog
        fields = [
            'log_id', 'user_id', 'user_type', 'action', 'entity_type',
            'entity_id', 'ip_address', 'user_agent', 'request_data',
            'response_status', 'created_at'
        ]
        read_only_fields = ['log_id', 'created_at']