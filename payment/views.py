"""
payment/views.py
────────────────────────────────────────────────────────────────────────────
Checkout flow:

  1. checkout           → shipping form (Step 1)
  2. billing_info       → saves shipping, renders payment page (Step 2)
  3. process_order      → finalises order (direct placement / test suite)
  4. payment_success    → confirmation page
  5. payment_failed     → failure page
  6. orders / order_detail → order history

MTN MoMo Collection Widget:
  7. momo_pay_page      → renders the widget sandbox page
  8. confirm_momo_payment → POST endpoint for widget event confirmation
"""

import json
import logging
import re
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from cart.cart import Cart
from store.models import Product

from .forms import ShippingForm
from .models import MoMoPayment, Order, OrderItem, ShippingAddress

logger = logging.getLogger(__name__)


# ── Checkout (Step 1: Shipping) ───────────────────────────────────────────────

def checkout(request):
    cart = Cart(request)
    cart_products = cart.get_products()
    quantities = cart.get_quants()
    totals = cart.totals()

    if len(cart) == 0:
        messages.warning(request, "Your cart is empty. Add some items before checking out.")
        return redirect('cart_summary')

    if request.user.is_authenticated:
        try:
            shipping = ShippingAddress.objects.filter(user=request.user).last()
            shipping_form = ShippingForm(instance=shipping)
        except ShippingAddress.DoesNotExist:
            shipping_form = ShippingForm()
    else:
        shipping_form = ShippingForm()

    return render(request, 'payment/checkout.html', {
        'cart_products': cart_products,
        'quantities': quantities,
        'totals': totals,
        'shipping_form': shipping_form,
    })


# ── Billing Info (Step 2: Save Shipping → Show Payment Page) ─────────────────

def billing_info(request):
    """
    POST from checkout.html shipping form.
    Validates + saves ShippingAddress, then renders billing_info.html where
    the customer proceeds with payment.
    """
    if request.method == 'POST':
        cart = Cart(request)
        cart_products = cart.get_products()
        quantities = cart.get_quants()
        totals = cart.totals()

        # Stock validation
        for product in cart_products:
            qty = quantities.get(str(product.id), 0)
            if product.stock < int(qty):
                messages.error(
                    request,
                    f"Sorry, only {product.stock} units of '{product.name}' are available."
                )
                return redirect('checkout')

        shipping_form = ShippingForm(request.POST)
        if shipping_form.is_valid():
            shipping = shipping_form.save(commit=False)
            if request.user.is_authenticated:
                shipping.user = request.user
            shipping.save()
            request.session['shipping_id'] = shipping.id
            request.session['shipping_info'] = request.POST.dict()
        else:
            messages.error(request, "Please correct the errors in your shipping information.")
            return redirect('checkout')

        return render(request, 'payment/billing_info.html', {
            'cart_products': cart_products,
            'quantities': quantities,
            'totals': totals,
            'shipping_info': request.POST,
        })
    else:
        messages.warning(request, "Access denied.")
        return redirect('checkout')


# ── Order Finalisation Helpers ────────────────────────────────────────────────

@transaction.atomic
def _finalize_order(request):
    """
    Creates Order, OrderItems, deducts stock, and clears the cart from session.
    """
    cart = Cart(request)
    cart_products = cart.get_products()
    quantities = cart.get_quants()
    totals = cart.totals()

    shipping_id = request.session.get('shipping_id')
    if not shipping_id:
        raise ValueError("Shipping information missing from session.")

    shipping = get_object_or_404(ShippingAddress, id=shipping_id)

    address_text = (
        f"{shipping.shipping_address1}, "
        f"{shipping.shipping_address2 + ', ' if shipping.shipping_address2 else ''}"
        f"{shipping.shipping_city}, {shipping.shipping_state} {shipping.shipping_postal_code}, "
        f"{shipping.shipping_country}"
    )

    order = Order.objects.create(
        user=request.user if request.user.is_authenticated else None,
        shipping_address=shipping,
        full_name=shipping.shipping_full_name,
        email=shipping.shipping_email,
        shipping_address_text=address_text,
        amount_paid=totals,
        is_paid=True,
        status=Order.STATUS_PROCESSING,
    )

    # Create OrderItems and decrement stock atomically
    for product in cart_products:
        qty = int(quantities.get(str(product.id), 1))
        price = product.sale_price if product.is_sale else product.price

        OrderItem.objects.create(
            order=order,
            product=product,
            price=price,
            quantity=qty,
        )

        from django.db.models import F
        Product.objects.filter(pk=product.pk).update(stock=F('stock') - qty)

    # Clear cart session
    request.session['session_key'] = {}

    if request.user.is_authenticated:
        from store.models import Profile
        try:
            profile = Profile.objects.get(user=request.user)
            profile.old_cart = ''
            profile.save()
        except Profile.DoesNotExist:
            pass

    request.session.pop('shipping_id', None)
    request.session.pop('shipping_info', None)

    return order


# ── Process Order ─────────────────────────────────────────────────────────────

def process_order(request):
    """
    Direct order placement.
    Used by the automated test suite (test_full_order_creation_flow).
    A new payment gateway integration should call _finalize_order() after
    payment confirmation.
    """
    if request.method == 'POST':
        try:
            order = _finalize_order(request)
        except (ValueError, ShippingAddress.DoesNotExist):
            messages.error(request, "Shipping information missing. Please start checkout again.")
            return redirect('checkout')

        messages.success(request, f"Order #{order.invoice_number} placed successfully! 🎉")
        return redirect('payment_success')
    else:
        messages.warning(request, "Access denied.")
        return redirect('checkout')


def payment_success(request):
    return render(request, 'payment/payment_success.html')


def payment_failed(request):
    return render(request, 'payment/payment_failed.html')


# ── Order History ─────────────────────────────────────────────────────────────

@login_required
def orders(request):
    user_orders = Order.objects.filter(user=request.user).prefetch_related('items__product')
    return render(request, 'payment/orders.html', {'orders': user_orders})


@login_required
def order_detail(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    items = order.items.select_related('product')
    return render(request, 'payment/order_detail.html', {'order': order, 'items': items})


# ═══════════════════════════════════════════════════════════════════════════════
# MTN MoMo Collection Widget — sandbox payment page + confirmation endpoint
# ═══════════════════════════════════════════════════════════════════════════════

def _generate_external_id():
    """Generate a unique, URL/JSON-safe order reference."""
    date_part = datetime.now().strftime('%Y%m%d')
    rand_part = uuid.uuid4().hex[:8].upper()
    return f"ORD-{date_part}-{rand_part}"


def momo_pay_page(request):
    """
    Renders the MoMo Collection Widget sandbox payment page.

    Reads `amount` from GET params (defaults to MOMO_DEMO_AMOUNT).
    Generates a unique external_id per page load, persists it in
    both the session and the MoMoPayment model.
    """
    # ── Validate amount ──────────────────────────────────────────────────
    raw_amount = request.GET.get('amount', settings.MOMO_DEMO_AMOUNT)
    try:
        amount = Decimal(raw_amount)
        if amount <= 0:
            raise ValueError('non-positive')
        # Enforce max 2 decimal places
        if amount != amount.quantize(Decimal('0.01')):
            raise ValueError('too many decimals')
        # Sensible upper bound for sandbox testing
        if amount > Decimal('1000000'):
            raise ValueError('exceeds max')
    except (InvalidOperation, ValueError):
        amount = Decimal(settings.MOMO_DEMO_AMOUNT)

    # ── Generate external_id (unique per page load) ──────────────────────
    external_id = _generate_external_id()

    # Store in session so confirm_momo_payment can verify ownership
    request.session['momo_external_id'] = external_id

    # Persist payment record
    MoMoPayment.objects.create(
        external_id=external_id,
        amount=amount,
        currency=settings.MOMO_CURRENCY,
        status=MoMoPayment.STATUS_CREATED,
        user=request.user if request.user.is_authenticated else None,
    )

    context = {
        'external_id': external_id,
        'amount': str(amount),
        'currency': settings.MOMO_CURRENCY,
        'api_user_id': settings.MOMO_SANDBOX_API_USER_ID,
        'widget_script_url': settings.MOMO_WIDGET_SCRIPT_URL,
    }
    return render(request, 'payment/momo_pay.html', context)


def verify_with_momo_collection_api(external_id):
    """
    TODO: Implement server-side payment verification.

    This function should call the MTN MoMo Collection API to verify that
    the payment identified by `external_id` was actually completed.

    Specifically, you need to:
    1. Use the Collections → GET /v1_0/requesttopay/{referenceId} endpoint
       to check the transaction status.
    2. Or implement a callback webhook that MTN MoMo POSTs to when the
       payment status changes.

    Documentation:
      https://momodeveloper.mtn.com → Collections API → RequestToPay

    Until this is implemented, the `MoMoPayment.verified` field will remain
    False, and orders should NOT be fulfilled based on client-side events alone.

    Returns:
        bool: True if the MoMo API confirms the payment as SUCCESSFUL.
    """
    logger.warning(
        'verify_with_momo_collection_api(%s): STUB — server-side verification '
        'not yet implemented. Payment recorded as pending_verification.',
        external_id,
    )
    return False


@require_POST
def confirm_momo_payment(request):
    """
    POST /payment/momo/confirm/

    Called by the widget JS when a lifecycle event fires.
    Expects JSON: { "external_id": "...", "invoice_id": "...", "status": "..." }

    SECURITY: The browser event is NOT proof of payment. This endpoint records
    the client-reported status as "pending_verification" and calls the
    verify_with_momo_collection_api() stub. The order should only be marked
    as paid after server-side verification succeeds.
    """
    # ── Parse JSON body ──────────────────────────────────────────────────
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Invalid JSON.'}, status=400)

    external_id = str(body.get('external_id', '')).strip()
    invoice_id  = str(body.get('invoice_id', '')).strip()
    status      = str(body.get('status', '')).strip().lower()

    # ── Validate ─────────────────────────────────────────────────────────
    if not external_id:
        return JsonResponse({'ok': False, 'error': 'Missing external_id.'}, status=400)

    # Basic format check: ORD-YYYYMMDD-HEXHEXHX
    if not re.match(r'^ORD-\d{8}-[A-F0-9]{8}$', external_id):
        return JsonResponse({'ok': False, 'error': 'Invalid external_id format.'}, status=400)

    valid_statuses = {'successful', 'failed', 'canceled', 'created'}
    if status not in valid_statuses:
        return JsonResponse(
            {'ok': False, 'error': f'Invalid status. Must be one of: {valid_statuses}'},
            status=400,
        )

    # ── Check session ownership ──────────────────────────────────────────
    session_ext_id = request.session.get('momo_external_id', '')
    if external_id != session_ext_id:
        logger.warning(
            'confirm_momo_payment: external_id mismatch — body=%s session=%s',
            external_id, session_ext_id,
        )
        return JsonResponse(
            {'ok': False, 'error': 'external_id does not match this session.'},
            status=400,
        )

    # ── Update payment record ────────────────────────────────────────────
    try:
        payment = MoMoPayment.objects.get(external_id=external_id)
    except MoMoPayment.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Payment not found.'}, status=404)

    # Map widget status to model status
    status_map = {
        'successful': MoMoPayment.STATUS_PENDING,  # "pending verification" until server confirms
        'failed':     MoMoPayment.STATUS_FAILED,
        'canceled':   MoMoPayment.STATUS_CANCELED,
        'created':    MoMoPayment.STATUS_CREATED,
    }
    payment.status = status_map.get(status, MoMoPayment.STATUS_CREATED)
    payment.invoice_id = invoice_id
    payment.save(update_fields=['status', 'invoice_id', 'updated_at'])

    logger.info(
        'confirm_momo_payment: external_id=%s widget_status=%s invoice_id=%s',
        external_id, status, invoice_id,
    )

    # ── Server-side verification (stub) ──────────────────────────────────
    verified = False
    if status == 'successful':
        verified = verify_with_momo_collection_api(external_id)
        if verified:
            payment.verified = True
            payment.status = MoMoPayment.STATUS_SUCCESS
            payment.save(update_fields=['verified', 'status', 'updated_at'])

    return JsonResponse({
        'ok': True,
        'state': payment.status,
        'verified': payment.verified,
    })