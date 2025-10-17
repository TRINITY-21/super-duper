from rest_framework import viewsets, status, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.pagination import PageNumberPagination
from rest_framework_simplejwt.tokens import RefreshToken
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Count, Q
from datetime import timedelta
import hashlib

from .models import (
    Supplier, Product, ProductFile, Test, 
    TestHistory, Report, Notification, AuditLog
)
from .serializers import (
    SupplierRegistrationSerializer, SupplierSerializer,
    ProductListSerializer, ProductDetailSerializer, ProductCreateSerializer,
    ProductFileSerializer, TestSerializer, TestListSerializer,
    ReportSerializer, NotificationSerializer, AuditLogSerializer
)


class StandardResultsSetPagination(PageNumberPagination):
    """Standard pagination for list views"""
    page_size = 20
    page_size_query_param = 'limit'
    max_page_size = 100


@api_view(['POST'])
@permission_classes([AllowAny])
def register_supplier(request):
    """Register a new supplier"""
    serializer = SupplierRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        supplier = serializer.save()
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(supplier)
        
        return Response({
            'supplier_id': str(supplier.supplier_id),
            'username': supplier.username,
            'email': supplier.email,
            'token': str(refresh.access_token),
            'refresh': str(refresh),
            'created_at': supplier.created_at
        }, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_supplier(request):
    """Login supplier and return JWT token"""
    from django.contrib.auth import authenticate
    
    username = request.data.get('username')
    password = request.data.get('password')
    
    if not username or not password:
        return Response({
            'error': {
                'code': 'VALIDATION_ERROR',
                'message': 'Username and password required'
            }
        }, status=status.HTTP_400_BAD_REQUEST)
    
    user = authenticate(username=username, password=password)
    
    if user is None:
        return Response({
            'error': {
                'code': 'UNAUTHORIZED',
                'message': 'Invalid credentials'
            }
        }, status=status.HTTP_401_UNAUTHORIZED)
    
    refresh = RefreshToken.for_user(user)
    
    return Response({
        'token': str(refresh.access_token),
        'refresh': str(refresh),
        'supplier': {
            'supplier_id': str(user.supplier_id),
            'username': user.username,
            'email': user.email
        }
    })


class SupplierViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for supplier operations"""
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'supplier_id'

    def get_queryset(self):
        # Users can only see their own profile
        if self.request.user.is_staff:
            return Supplier.objects.all()
        return Supplier.objects.filter(supplier_id=self.request.user.supplier_id)


class ProductViewSet(viewsets.ModelViewSet):
    """ViewSet for product operations"""
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'category', 'sku']
    ordering_fields = ['created_at', 'submission_date', 'name']
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = Product.objects.select_related('supplier').prefetch_related('tests', 'files')
        
        # Filter by supplier
        if not self.request.user.is_staff:
            queryset = queryset.filter(supplier=self.request.user)
        
        # Filter by status
        submission_status = self.request.query_params.get('status', None)
        if submission_status:
            queryset = queryset.filter(submission_status=submission_status)
        
        # Filter by category
        category = self.request.query_params.get('category', None)
        if category:
            queryset = queryset.filter(category=category)
        
        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return ProductListSerializer
        elif self.action == 'create':
            return ProductCreateSerializer
        return ProductDetailSerializer

    def perform_create(self, serializer):
        serializer.save(supplier=self.request.user)

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Submit product for testing"""
        product = self.get_object()
        
        if product.submission_status != 'draft':
            return Response({
                'error': {
                    'code': 'INVALID_STATE',
                    'message': 'Product already submitted or cannot be submitted'
                }
            }, status=status.HTTP_400_BAD_REQUEST)
        
        product.submission_status = 'submitted'
        product.submission_date = timezone.now()
        product.save()
        
        # Create notification
        Notification.objects.create(
            recipient_id=product.supplier.supplier_id,
            recipient_type='supplier',
            notification_type='product_submitted',
            subject='Product Submitted',
            message=f'Your product "{product.name}" has been submitted for testing.',
            status='sent',
            sent_at=timezone.now()
        )
        
        serializer = ProductDetailSerializer(product)
        return Response({
            **serializer.data,
            'message': 'Product submitted successfully for testing'
        })

    @action(detail=True, methods=['get'])
    def tests(self, request, pk=None):
        """Get all tests for a product"""
        product = self.get_object()
        tests = product.tests.all()
        
        serializer = TestListSerializer(tests, many=True)
        
        # Calculate summary
        total_tests = tests.count()
        completed = tests.filter(status='completed').count()
        in_progress = tests.filter(status='in_progress').count()
        pending = tests.filter(status__in=['pending', 'scheduled']).count()
        passed = tests.filter(result_status='pass').count()
        
        pass_rate = round((passed / total_tests * 100)) if total_tests > 0 else 0
        
        return Response({
            'product_id': str(product.product_id),
            'tests': serializer.data,
            'summary': {
                'total_tests': total_tests,
                'completed': completed,
                'in_progress': in_progress,
                'pending': pending,
                'pass_rate': f'{pass_rate}%'
            }
        })

    @action(detail=True, methods=['get'])
    def reports(self, request, pk=None):
        """Get all reports for a product"""
        product = self.get_object()
        reports = product.reports.all()
        serializer = ReportSerializer(reports, many=True, context={'request': request})
        
        return Response({
            'product_id': str(product.product_id),
            'reports': serializer.data
        })


class ProductFileViewSet(viewsets.ModelViewSet):
    """ViewSet for product file uploads"""
    serializer_class = ProductFileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        product_id = self.kwargs.get('product_pk')
        return ProductFile.objects.filter(product_id=product_id)

    def perform_create(self, serializer):
        product_id = self.kwargs.get('product_pk')
        product = get_object_or_404(Product, product_id=product_id)
        
        # Check ownership
        if product.supplier != self.request.user and not self.request.user.is_staff:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You don't have permission to upload files for this product")
        
        file_obj = self.request.FILES.get('file')
        
        # Calculate file hash
        file_hash = hashlib.sha256(file_obj.read()).hexdigest()
        file_obj.seek(0)  # Reset file pointer
        
        # Determine file type
        file_extension = file_obj.name.split('.')[-1].upper()
        
        serializer.save(
            product=product,
            file_name=file_obj.name,
            file_type=file_extension,
            file_size=file_obj.size,
            file_hash=file_hash,
            upload_status='validated',
            validated_at=timezone.now()
        )


class TestViewSet(viewsets.ModelViewSet):
    """ViewSet for test operations"""
    serializer_class = TestSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = Test.objects.select_related('product').prefetch_related('history')
        
        # Filter by product if specified
        product_id = self.request.query_params.get('product_id', None)
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        
        # Filter by status
        test_status = self.request.query_params.get('status', None)
        if test_status:
            queryset = queryset.filter(status=test_status)
        
        # Filter by type
        test_type = self.request.query_params.get('type', None)
        if test_type:
            queryset = queryset.filter(test_type=test_type)
        
        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return TestListSerializer
        return TestSerializer

    def perform_create(self, serializer):
        test = serializer.save()
        
        # Create history entry
        TestHistory.objects.create(
            test=test,
            changed_by=self.request.user.username,
            change_type='test_created',
            new_status=test.status
        )

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """Start a test"""
        test = self.get_object()
        
        if test.status != 'scheduled':
            return Response({
                'error': {
                    'code': 'INVALID_STATE',
                    'message': 'Test is not in scheduled state'
                }
            }, status=status.HTTP_400_BAD_REQUEST)
        
        test.status = 'in_progress'
        test.started_at = timezone.now()
        test.save()
        
        # Create history
        TestHistory.objects.create(
            test=test,
            changed_by=request.user.username,
            change_type='test_started',
            old_status='scheduled',
            new_status='in_progress'
        )
        
        serializer = TestSerializer(test)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Complete a test with results"""
        test = self.get_object()
        
        result_status = request.data.get('result_status')
        result_summary = request.data.get('result_summary')
        result_data = request.data.get('result_data', {})
        
        if not result_status:
            return Response({
                'error': {
                    'code': 'VALIDATION_ERROR',
                    'message': 'result_status is required'
                }
            }, status=status.HTTP_400_BAD_REQUEST)
        
        test.status = 'completed'
        test.result_status = result_status
        test.result_summary = result_summary
        test.result_data = result_data
        test.completed_at = timezone.now()
        test.save()
        
        # Create history
        TestHistory.objects.create(
            test=test,
            changed_by=request.user.username,
            change_type='test_completed',
            old_status=test.status,
            new_status='completed',
            change_description=f'Test completed with {result_status} result'
        )
        
        # Send notification
        Notification.objects.create(
            recipient_id=test.product.supplier.supplier_id,
            recipient_type='supplier',
            notification_type='test_completed',
            subject=f'Test Completed: {test.test_name}',
            message=f'Your product "{test.product.name}" has completed {test.test_name} with {result_status} result.',
            status='sent',
            sent_at=timezone.now()
        )
        
        serializer = TestSerializer(test)
        return Response(serializer.data)


class ReportViewSet(viewsets.ModelViewSet):
    """ViewSet for report operations"""
    serializer_class = ReportSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = Report.objects.select_related('product')
        
        # Filter by product
        product_id = self.request.query_params.get('product_id', None)
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        
        # Filter by status
        report_status = self.request.query_params.get('status', None)
        if report_status:
            queryset = queryset.filter(status=report_status)
        
        return queryset

    def perform_create(self, serializer):
        report = serializer.save(status='generating')

        from threading import Timer
        
        def complete_report():
            report.status = 'completed'
            report.generated_at = timezone.now()
            report.expires_at = timezone.now() + timedelta(days=30)
            report.report_url = f'/api/v1/reports/{report.report_id}/download'
            report.save()
        
        # Simulate 5 second generation time
        Timer(5.0, complete_report).start()

    @action(detail=True, methods=['get'])
    def status_check(self, request, pk=None):
        """Check report generation status"""
        report = self.get_object()
        serializer = ReportSerializer(report, context={'request': request})
        
        response_data = serializer.data
        if report.status == 'completed':
            response_data['download_url'] = f'/api/v1/reports/{report.report_id}/download'
        
        return Response(response_data)

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Download report file"""
        report = self.get_object()
        
        if report.status != 'completed':
            return Response({
                'error': {
                    'code': 'NOT_READY',
                    'message': 'Report is not ready for download'
                }
            }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'report_id': str(report.report_id),
            'download_url': f'https://reports-bucket.s3.amazonaws.com/{report.s3_key}',
            'expires_in': '3600 seconds',
            'message': 'Use this URL to download the report'
        })


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for notifications"""
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        # Users see only their notifications
        return Notification.objects.filter(
            recipient_id=self.request.user.supplier_id,
            recipient_type='supplier'
        )

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark notification as read"""
        notification = self.get_object()
        notification.status = 'read'
        notification.read_at = timezone.now()
        notification.save()
        
        serializer = NotificationSerializer(notification)
        return Response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Health check endpoint"""
    from django.db import connection
    
    try:
        # Check database connection
        connection.ensure_connection()
        
        return Response({
            'status': 'healthy',
            'timestamp': timezone.now(),
            'database': 'connected'
        })
    except Exception as e:
        return Response({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': timezone.now()
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)