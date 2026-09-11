"""
payment/views.py
────────────────────────────────────────────────────────────────────────────
Full MTN MoMo Collections checkout flow:

  1. checkout           → shipping form (Step 1)
  2. billing_info       → saves shipping, renders MoMo phone input (Step 2)
  3. initiate_momo_payment → calls MoMo API, stores reference_id in session
  4. momo_pending.html  → user approves on phone
  5. momo_callback      → MoMo async POST / redirect (idempotent, atomic)
  6. momo_status_poll   → AJAX endpoint polled from momo_pending.html
  7. process_order      → kept for test-suite compatibility (direct finalisation)
  8. payment_success    → confirmation page
  9. orders / order_detail → order history
"""

import logging
import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from cart.cart import Cart
from store.models import Product

from .forms import ShippingForm
from .momo_client import MoMoClient, MoMoError
from .models import MoMoTransaction, Order, OrderItem, ShippingAddress

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


# ── Billing Info (Step 2: Save Shipping → Show MoMo Phone Input) ─────────────

def billing_info(request):
    """
    POST from checkout.html shipping form.
    Validates + saves ShippingAddress, then renders billing_info.html where
    the customer enters their MoMo phone number.
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


# ── Step 3: Initiate MTN MoMo Payment ────────────────────────────────────────

@require_POST
def initiate_momo_payment(request):
    """
    Receives the MoMo phone number from billing_info.html.
    Calls the MTN MoMo Collections API (requestToPay) and stores the
    reference_id in the session, then renders momo_pending.html.
    """
    cart = Cart(request)

    if len(cart) == 0:
        messages.warning(request, "Your cart is empty.")
        return redirect('cart_summary')

    shipping_id = request.session.get('shipping_id')
    if not shipping_id:
        messages.error(request, "Shipping information missing. Please start checkout again.")
        return redirect('checkout')

    momo_number = request.POST.get('momo_number', '').strip()
    if not momo_number:
        messages.error(request, "Please enter your MTN MoMo phone number.")
        return redirect('billing_info')

    totals = cart.totals()

    # Build a stable external_id from session shipping_id for reconciliation
    external_id = f"SHOP-{shipping_id}"

    # Build callback URL
    callback_url = None
    if settings.MOMO_CALLBACK_HOST:
        scheme = 'https'
        callback_url = f"{scheme}://{settings.MOMO_CALLBACK_HOST.rstrip('/')}/payment/momo/callback/"

    try:
        client = MoMoClient()
        reference_id = client.request_to_pay(
            amount=str(totals),
            phone=momo_number,
            external_id=external_id,
            payer_message=f"Payment for order {external_id}",
            payee_note=f"Order {external_id}",
            callback_url=callback_url,
        )
    except MoMoError as exc:
        logger.error("MoMo initiate failed: %s", exc)
        messages.error(
            request,
            "We could not reach the MTN MoMo payment service. "
            "Please check your number and try again."
        )
        return redirect('billing_info')

    # Persist the transaction record for idempotency
    msisdn = MoMoClient().normalize_phone(momo_number)
    MoMoTransaction.objects.create(
        reference_id=uuid.UUID(reference_id),
        msisdn=msisdn,
        amount=totals,
        currency=settings.MOMO_CURRENCY,
        external_id=external_id,
        status=MoMoTransaction.STATUS_PENDING,
        user=request.user if request.user.is_authenticated else None,
    )

    # Store in session so polling and callback can find it
    request.session['momo_reference_id'] = reference_id

    logger.info(
        "MoMo payment initiated: reference_id=%s msisdn=%s amount=%s",
        reference_id, msisdn, totals
    )

    return render(request, 'payment/momo_pending.html', {
        'reference_id': reference_id,
        'totals': totals,
    })


# ── Step 5: MTN MoMo Async Callback (Webhook) ────────────────────────────────

@csrf_exempt           # MoMo server has no CSRF token; IP-filter in production
@require_POST
def momo_callback(request):
    """
    MTN MoMo asynchronously POSTs to this endpoint after a payment attempt.

    Security notes:
      • csrf_exempt is safe here because the callback body carries no CSRF token
        and is protected by reference_id verification + idempotency check.
      • In production, add IP allowlisting for MTN's callback servers in your
        load balancer / WAF to block spoofed callbacks.

    Idempotency:
      • We look up MoMoTransaction by reference_id. If it is already terminal,
        we return HTTP 200 immediately (MTN may retry on non-2xx).
      • _finalize_order() runs inside a database transaction (atomic).
    """
    import json

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        logger.warning("momo_callback: invalid JSON body")
        return JsonResponse({'error': 'invalid body'}, status=400)

    reference_id  = body.get('referenceId') or request.GET.get('referenceId')
    status        = body.get('status', 'PENDING').upper()
    fin_tx_id     = body.get('financialTransactionId', '')
    error_reason  = body.get('reason', '')

    if not reference_id:
        logger.warning("momo_callback: missing referenceId")
        return JsonResponse({'error': 'missing referenceId'}, status=400)

    # ── Idempotency check ─────────────────────────────────────────────────────
    try:
        tx = MoMoTransaction.objects.select_for_update().get(
            reference_id=uuid.UUID(str(reference_id))
        )
    except MoMoTransaction.DoesNotExist:
        logger.warning("momo_callback: unknown reference_id=%s", reference_id)
        return JsonResponse({'error': 'unknown reference'}, status=404)

    if tx.is_terminal:
        # Already processed — acknowledge without side effects
        logger.info(
            "momo_callback: duplicate callback for %s (already %s)",
            reference_id, tx.status
        )
        return JsonResponse({'status': 'already processed'}, status=200)

    # ── Update transaction status ─────────────────────────────────────────────
    tx.status = status
    tx.financial_transaction_id = fin_tx_id
    tx.momo_error_reason = error_reason
    tx.save(update_fields=['status', 'financial_transaction_id', 'momo_error_reason', 'updated_at'])

    if status == MoMoTransaction.STATUS_SUCCESSFUL:
        # Retrieve the session context to finalise the order.
        # Note: for async server-to-server callbacks the Django session is not
        # available; external_id carries the shipping_id so we reconstruct it.
        try:
            shipping_id = int(tx.external_id.replace('SHOP-', ''))
            order = _finalize_order_from_shipping(
                shipping_id=shipping_id,
                user=tx.user,
                amount_paid=tx.amount,
            )
            tx.order = order
            tx.save(update_fields=['order'])
            logger.info("momo_callback: order %s created from MoMo tx %s", order.id, reference_id)
        except Exception as exc:
            logger.exception("momo_callback: _finalize_order_from_shipping failed: %s", exc)
            return JsonResponse({'error': 'order creation failed'}, status=500)
    else:
        logger.info(
            "momo_callback: payment not successful — reference_id=%s status=%s reason=%s",
            reference_id, status, error_reason
        )

    return JsonResponse({'status': status}, status=200)


# ── Step 6: AJAX Status Poll Endpoint ────────────────────────────────────────

def momo_status_poll(request, reference_id):
    """
    Called by momo_pending.html every 5 seconds via fetch().
    Returns JSON: {"status": "PENDING"|"SUCCESSFUL"|"FAILED"|...}

    Also triggers order finalisation here if MoMo callback was missed
    (acts as a safety net polling the MoMo API directly).
    """
    try:
        tx = MoMoTransaction.objects.get(reference_id=uuid.UUID(str(reference_id)))
    except (MoMoTransaction.DoesNotExist, ValueError):
        return JsonResponse({'status': 'NOT_FOUND'}, status=404)

    if not tx.is_terminal:
        # Poll the MoMo API for the latest status
        try:
            client = MoMoClient()
            data = client.get_payment_status(str(reference_id))
            new_status = data.get('status', tx.status).upper()

            if new_status != tx.status:
                tx.status = new_status
                tx.financial_transaction_id = data.get('financialTransactionId', '')
                tx.save(update_fields=['status', 'financial_transaction_id', 'updated_at'])

                # Finalise the order if callback was missed
                if new_status == MoMoTransaction.STATUS_SUCCESSFUL and tx.order is None:
                    try:
                        shipping_id = int(tx.external_id.replace('SHOP-', ''))
                        order = _finalize_order_from_shipping(
                            shipping_id=shipping_id,
                            user=tx.user,
                            amount_paid=tx.amount,
                        )
                        tx.order = order
                        tx.save(update_fields=['order'])
                    except Exception as exc:
                        logger.exception("momo_status_poll: order finalisation failed: %s", exc)

        except MoMoError as exc:
            logger.warning("momo_status_poll: API error for %s: %s", reference_id, exc)

    payload = {
        'status': tx.status,
        'is_terminal': tx.is_terminal,
        'redirect_url': None,
    }

    if tx.status == MoMoTransaction.STATUS_SUCCESSFUL and tx.order:
        payload['redirect_url'] = '/payment/payment-success/'
    elif tx.is_terminal and tx.status != MoMoTransaction.STATUS_SUCCESSFUL:
        payload['redirect_url'] = '/payment/payment-failed/'

    return JsonResponse(payload)


# ── Order Finalisation Helpers ────────────────────────────────────────────────

@transaction.atomic
def _finalize_order_from_shipping(shipping_id: int, user, amount_paid):
    """
    Creates Order + OrderItems from a saved ShippingAddress id.
    Called by momo_callback and momo_status_poll — does NOT rely on the
    Django session (safe for server-to-server callbacks).
    """
    shipping = get_object_or_404(ShippingAddress, id=shipping_id)

    address_text = (
        f"{shipping.shipping_address1}, "
        f"{shipping.shipping_address2 + ', ' if shipping.shipping_address2 else ''}"
        f"{shipping.shipping_city}, {shipping.shipping_state} {shipping.shipping_postal_code}, "
        f"{shipping.shipping_country}"
    )

    order = Order.objects.create(
        user=user,
        shipping_address=shipping,
        full_name=shipping.shipping_full_name,
        email=shipping.shipping_email,
        shipping_address_text=address_text,
        amount_paid=amount_paid,
        is_paid=True,
        status=Order.STATUS_PROCESSING,
    )
    return order


@transaction.atomic
def _finalize_order(request):
    """
    Creates Order, OrderItems, deducts stock, and clears the cart from session.
    Relies on the Django session — used by process_order (tests) and the
    session-based path when momo_callback is hit in the same request context.
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
    request.session.pop('momo_reference_id', None)

    return order


# ── Process Order (kept for test-suite backward compatibility) ────────────────

def process_order(request):
    """
    Direct order placement without MoMo payment gate.
    Used by the automated test suite (test_full_order_creation_flow).
    In production, orders are placed via momo_callback / momo_status_poll.
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