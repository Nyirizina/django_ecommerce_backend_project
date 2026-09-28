from django.urls import path
from .auth_views import RegisterView, MeView

urlpatterns = [
    path('auth/register/', RegisterView.as_view(), name='api-auth-register'),
    path('auth/me/', MeView.as_view(), name='api-auth-me'),
]
