from django.urls import path
from .api_views import OrderListAPIView, OrderDetailAPIView
from .checkout_api_view import CheckoutAPIView

urlpatterns = [
    path('orders/', OrderListAPIView.as_view(), name='api-orders'),
    path('orders/<int:pk>/', OrderDetailAPIView.as_view(), name='api-order-detail'),
    path('checkout/', CheckoutAPIView.as_view(), name='api-checkout'),
]
