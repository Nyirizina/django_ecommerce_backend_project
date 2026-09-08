from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from cart.cart import Cart
from .forms import ShippingForm
from .models import ShippingAddress, Order, OrderItem
from store.models import Product
import json


# ── Checkout ─────────────────────────────────────────────────────────────────

def checkout(request):
    cart = Cart(request)
    cart_products = cart.get_products()
    quantities = cart.get_quants()
    totals = cart.totals()

    if len(cart) == 0:
        messages.warning(request, "Your cart is empty. Add some items before checking out.")
        return redirect('cart_summary')

    # Pre-populate shipping form from saved profile info
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


def billing_info(request):
    if request.method == 'POST':
        cart = Cart(request)
        cart_products = cart.get_products()
        quantities = cart.get_quants()
        totals = cart.totals()

        # Validate stock before proceeding
        for product in cart_products:
            qty = quantities.get(str(product.id), 0)
            if product.stock < int(qty):
                messages.error(request, f"Sorry, only {product.stock} units of '{product.name}' are available.")
                return redirect('checkout')

        # Save shipping form data to session for order creation
        shipping_form = ShippingForm(request.POST)
        if shipping_form.is_valid():
            # Save the address
            shipping = shipping_form.save(commit=False)
            if request.user.is_authenticated:
                shipping.user = request.user
            shipping.save()

            # Store address id in session
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


# ── Order Processing ──────────────────────────────────────────────────────────

def process_order(request):
    if request.method == 'POST':
        cart = Cart(request)
        cart_products = cart.get_products()
        quantities = cart.get_quants()
        totals = cart.totals()

        # Get saved shipping address
        shipping_id = request.session.get('shipping_id')
        shipping_info = request.session.get('shipping_info', {})

        if not shipping_id:
            messages.error(request, "Shipping information missing. Please start checkout again.")
            return redirect('checkout')

        try:
            shipping = ShippingAddress.objects.get(id=shipping_id)
        except ShippingAddress.DoesNotExist:
            messages.error(request, "Shipping address not found.")
            return redirect('checkout')

        # Compose address snapshot text
        address_text = (
            f"{shipping.shipping_address1}, "
            f"{shipping.shipping_address2 + ', ' if shipping.shipping_address2 else ''}"
            f"{shipping.shipping_city}, {shipping.shipping_state} {shipping.shipping_postal_code}, "
            f"{shipping.shipping_country}"
        )

        # Create the Order
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

        # Create OrderItems and decrement stock
        for product in cart_products:
            qty = int(quantities.get(str(product.id), 1))
            price = product.sale_price if product.is_sale else product.price

            OrderItem.objects.create(
                order=order,
                product=product,
                price=price,
                quantity=qty,
            )

            # Deduct stock
            product.stock = max(0, product.stock - qty)
            product.save()

        # Clear the cart
        request.session['session_key'] = {}

        # Clear saved cart from profile
        if request.user.is_authenticated:
            from store.models import Profile
            try:
                profile = Profile.objects.get(user=request.user)
                profile.old_cart = ''
                profile.save()
            except Profile.DoesNotExist:
                pass

        # Clean up session
        if 'shipping_id' in request.session:
            del request.session['shipping_id']
        if 'shipping_info' in request.session:
            del request.session['shipping_info']

        messages.success(request, f"Order #{order.invoice_number} placed successfully! 🎉")
        return redirect('payment_success')

    else:
        messages.warning(request, "Access denied.")
        return redirect('checkout')


def payment_success(request):
    return render(request, 'payment/payment_success.html')


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