from django.urls import path
from . import views

urlpatterns = [
    # ── Core checkout flow ────────────────────────────────────────────────────
    path('checkout/', views.checkout, name='checkout'),
    path('billing-info/', views.billing_info, name='billing_info'),
    path('payment-success/', views.payment_success, name='payment_success'),
    path('payment-failed/', views.payment_failed, name='payment_failed'),

    # ── Order processing ─────────────────────────────────────────────────────
    path('process-order/', views.process_order, name='process_order'),

    # ── MTN MoMo Collection Widget ───────────────────────────────────────────
    path('momo/pay/', views.momo_pay_page, name='momo_pay'),
    path('momo/confirm/', views.confirm_momo_payment, name='confirm_momo_payment'),

    # ── Order history ─────────────────────────────────────────────────────────
    path('orders/', views.orders, name='orders'),
    path('orders/<int:pk>/', views.order_detail, name='order_detail'),
]