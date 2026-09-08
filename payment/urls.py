from django.urls import path
from . import views

urlpatterns = [
    path('checkout/', views.checkout, name='checkout'),
    path('billing-info/', views.billing_info, name='billing_info'),
    path('process-order/', views.process_order, name='process_order'),
    path('payment-success/', views.payment_success, name='payment_success'),
    path('orders/', views.orders, name='orders'),
    path('orders/<int:pk>/', views.order_detail, name='order_detail'),
]