from django.urls import path
from . import views

urlpatterns = [
    # ── Core checkout flow ────────────────────────────────────────────────────
    path('checkout/', views.checkout, name='checkout'),
    path('billing-info/', views.billing_info, name='billing_info'),
    path('payment-success/', views.payment_success, name='payment_success'),
    path('payment-failed/', views.payment_failed, name='payment_failed'),

    # ── MTN MoMo integration ──────────────────────────────────────────────────
    # Step 3: Receives phone number from billing_info.html, calls MoMo API
    path('momo/initiate/', views.initiate_momo_payment, name='initiate_momo_payment'),
    # Step 5: MTN MoMo server POSTs here after payment attempt (async webhook)
    path('momo/callback/', views.momo_callback, name='momo_callback'),
    # Step 6: AJAX polling — called every 5s from momo_pending.html
    path('momo/status/<str:reference_id>/', views.momo_status_poll, name='momo_status_poll'),

    # ── Order processing (kept for backward compat / test suite) ─────────────
    path('process-order/', views.process_order, name='process_order'),

    # ── Order history ─────────────────────────────────────────────────────────
    path('orders/', views.orders, name='orders'),
    path('orders/<int:pk>/', views.order_detail, name='order_detail'),
]