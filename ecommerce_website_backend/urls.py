
from django.contrib import admin
from django.urls import path, include
from . import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('store.urls')),
    path('cart/', include('cart.urls')),
    path('payment/', include('payment.urls')),

    # ── REST API ──────────────────────────────────────────────────────────────
    # JWT authentication endpoints (SimpleJWT built-ins)
    path('api/auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    # Custom auth endpoints: register + me
    path('api/', include('store.auth_urls')),
    # Products & categories
    path('api/', include('store.api_urls')),
    # Cart (session-based REST wrapper)
    path('api/', include('cart.api_urls')),
    # Orders & checkout
    path('api/', include('payment.api_urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
