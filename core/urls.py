from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_nested import routers

from . import views

router = DefaultRouter()
router.register(r'suppliers', views.SupplierViewSet, basename='supplier')
router.register(r'products', views.ProductViewSet, basename='product')
router.register(r'tests', views.TestViewSet, basename='test')
router.register(r'reports', views.ReportViewSet, basename='report')
router.register(r'notifications', views.NotificationViewSet, basename='notification')

products_router = routers.NestedDefaultRouter(router, r'products', lookup='product')
products_router.register(r'files', views.ProductFileViewSet, basename='product-files')

urlpatterns = [
    # Authentication
    path('auth/register/', views.register_supplier, name='register'),
    path('auth/login/', views.login_supplier, name='login'),
    path('auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Health check
    path('health/', views.health_check, name='health'),
    
    # API routes
    path('', include(router.urls)),
    path('', include(products_router.urls)),
]


