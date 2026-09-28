"""
payment/checkout_api_view.py
───────────────────────────────────────────────────────────────────────────────
REST endpoint for placing an order from the Next.js frontend.

  POST /api/checkout/
  Body (JSON):
    {
      "shipping_address": {
        "first_name", "last_name", "email",
        "address_line1", "address_line2"?,
        "city", "region"?, "postal_code", "country", "phone"?
      },
      "payment_reference": "COD"   // or a MoMo reference
    }

  The view reads cart items from the Django SESSION cart so the browser session
  cookie must be sent (CORS_ALLOW_CREDENTIALS = True covers this for localhost).
  On success it creates ShippingAddress + Order + OrderItem rows, clears the
  session cart, and returns the serialised Order.

  Permission: AllowAny (supports guest checkout).
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import transaction
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from cart.cart import Cart
from payment.models import Order, OrderItem, ShippingAddress
from payment.serializers import OrderSerializer
from store.models import Product


class ShippingAddressInputSerializer(serializers.Serializer):
    first_name   = serializers.CharField()
    last_name    = serializers.CharField()
    email        = serializers.EmailField()
    phone        = serializers.CharField(required=False, allow_blank=True)
    address_line1 = serializers.CharField()
    address_line2 = serializers.CharField(required=False, allow_blank=True)
    city         = serializers.CharField()
    region       = serializers.CharField(required=False, allow_blank=True)
    postal_code  = serializers.CharField(required=False, allow_blank=True)
    country      = serializers.CharField()


class CheckoutAPIView(APIView):
    """POST /api/checkout/ — place an order."""
    permission_classes = [AllowAny]

    def post(self, request):
        # ── 1. Validate shipping address ──────────────────────────────────────
        addr_serializer = ShippingAddressInputSerializer(data=request.data.get('shipping_address', {}))
        if not addr_serializer.is_valid():
            return Response({'shipping_address': addr_serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        addr_data = addr_serializer.validated_data

        # ── 2. Read cart from session ─────────────────────────────────────────
        cart = Cart(request)
        product_ids = list(cart.cart.keys())
        if not product_ids:
            return Response({'error': 'Your cart is empty.'}, status=status.HTTP_400_BAD_REQUEST)

        products = {str(p.id): p for p in Product.objects.filter(id__in=product_ids)}
        quantities = cart.get_quants()

        # ── 3. Build order atomically ─────────────────────────────────────────
        payment_reference = request.data.get('payment_reference', 'COD')

        with transaction.atomic():
            # Create / update shipping address
            user = request.user if request.user.is_authenticated else None
            shipping = ShippingAddress.objects.create(
                user=user,
                shipping_full_name=f"{addr_data['first_name']} {addr_data['last_name']}",
                shipping_email=addr_data['email'],
                shipping_address1=addr_data['address_line1'],
                shipping_address2=addr_data.get('address_line2', ''),
                shipping_city=addr_data['city'],
                shipping_state=addr_data.get('region', ''),
                shipping_postal_code=addr_data.get('postal_code', ''),
                shipping_country=addr_data['country'],
            )

            # Compute total
            total = Decimal('0.00')
            line_items = []
            for pid_str, qty in quantities.items():
                product = products.get(pid_str)
                if not product:
                    continue
                price = product.sale_price if product.is_sale else product.price
                total += price * qty
                line_items.append((product, price, qty))

            # Create order
            order = Order.objects.create(
                user=user,
                shipping_address=shipping,
                full_name=f"{addr_data['first_name']} {addr_data['last_name']}",
                email=addr_data['email'],
                shipping_address_text=(
                    f"{addr_data['address_line1']}, {addr_data['city']}, {addr_data['country']}"
                ),
                amount_paid=total,
                is_paid=(payment_reference != 'COD'),
                status=Order.STATUS_PENDING,
            )

            # Create order items
            for product, price, qty in line_items:
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    price=price,
                    quantity=qty,
                )

            # Clear session cart
            cart.cart.clear()
            request.session.modified = True

        # ── 4. Return serialised order ────────────────────────────────────────
        data = OrderSerializer(order, context={'request': request}).data
        return Response(data, status=status.HTTP_201_CREATED)
