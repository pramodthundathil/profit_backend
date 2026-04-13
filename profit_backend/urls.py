from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView
from django.conf import settings
from django.conf.urls.static import static

from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from home import views_admin


# Swagger Configuration
schema_view = get_schema_view(
    openapi.Info(
        title="PRO-FIT GYM management",
        default_version='v1',
        description="""
        # PRO-FIT GYM management Platform API
        
        Complete API documentation for the PRO-FIT GYM management.
        
        ## Features
        - OTP-based authentication
        - Role-based access control (4 user roles)
    
        
        ## Authentication
        This API uses JWT (JSON Web Tokens) for authentication.
        
        ### Login Flow:
        1. Call /api/v1/auth/generate-otp/ with email/phone
        2. Receive OTP via email/SMS
        3. Call /api/v1/auth/verify-otp/ with OTP
        4. Receive access and refresh tokens
        5. Use access token in Authorization header: Bearer <token>
        
        ## User Roles
        - *Gym admin*: Full access to respective Gym
        - *Gym staff*: Limited access to gym
        - *Trainer*: member view and food log
        
        - *Admin*: Full system access
        """,
        terms_of_service="https://www.byteboot.in/",
        contact=openapi.Contact(email="support@byteboot.in"),
        license=openapi.License(name="Byteboot"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # API Documentation
    path('api/swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='swagger'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path('swagger.json', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger.yaml', schema_view.without_ui(cache_timeout=0), name='schema-yaml'),
    
    # API v1
    path('auth/users/', include('home.urls')),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    # path('api/v1/applications/', include('applications.urls')),
    path('v1/finance/', include('finance.urls')),
    path('v1/foodlog/', include('foodlog.urls')),
    path('v2/members/', include('members.urls')),
    path('v2/payments/', include('payments.urls')),
    path('v3/utils/', include('utils.urls')),
    path('v4/notifications/', include('notifications.urls')),
    path('enquiries/', include('enquiry.urls')),
    
    # path('api/v1/reports/', include('reports.urls')),

    #html pages rendering for admin and page users 
    path("",views_admin.signin, name="signin"),

]



if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)