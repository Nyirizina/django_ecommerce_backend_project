from rest_framework import serializers
from .models import Order, OrderItem, ShippingAddress


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_image = serializers.SerializerMethodField()
    line_total = serializers.SerializerMethodField()
    # G8: Frontend OrderItem type expects 'unit_price' (alias of 'price')
    unit_price = serializers.DecimalField(
        source='price', max_digits=10, decimal_places=2, read_only=True
    )
    # G9: Frontend OrderItem type expects optional 'product_slug'
    product_slug = serializers.CharField(source='product.slug', read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            'id', 'product', 'product_name', 'product_image',
            'price', 'quantity', 'line_total',
            # Additive fields for frontend compatibility
            'unit_price', 'product_slug',
        ]

    def get_product_image(self, obj):
        request = self.context.get('request')
        if obj.product.image and request:
            return request.build_absolute_uri(obj.product.image.url)
        return None

    def get_line_total(self, obj):
        return float(obj.get_total())


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    # ── Additive fields: bridge backend → frontend Order interface ────────
    # G1: Frontend expects 'total' (alias of amount_paid)
    total = serializers.SerializerMethodField()
    # G2: Frontend expects 'subtotal' (sum of item line totals)
    subtotal = serializers.SerializerMethodField()
    # G3: Frontend expects 'shipping_cost' (always 0 — free shipping)
    shipping_cost = serializers.SerializerMethodField()
    # G4: Frontend expects 'created_at' (alias of date_ordered)
    created_at = serializers.SerializerMethodField()
    # G5: Frontend expects 'shipping_address' as structured object
    shipping_address = serializers.SerializerMethodField()
    # G6: Frontend expects optional 'payment_reference'
    payment_reference = serializers.SerializerMethodField()
    # G7: Frontend expects lowercase status values
    status = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            # Original fields (kept for backward compatibility)
            'id', 'invoice_number', 'full_name', 'email',
            'shipping_address_text', 'amount_paid', 'is_paid',
            'date_ordered', 'items',
            # Additive fields for frontend compatibility
            'total', 'subtotal', 'shipping_cost', 'created_at',
            'shipping_address', 'payment_reference', 'status',
        ]

    # ── G1 ────────────────────────────────────────────────────────────────
    def get_total(self, obj):
        return float(obj.amount_paid)

    # ── G2 ────────────────────────────────────────────────────────────────
    def get_subtotal(self, obj):
        return float(sum(item.get_total() for item in obj.items.all()))

    # ── G3 ────────────────────────────────────────────────────────────────
    def get_shipping_cost(self, obj):
        return 0

    # ── G4 ────────────────────────────────────────────────────────────────
    def get_created_at(self, obj):
        return obj.date_ordered.isoformat()

    # ── G5 ────────────────────────────────────────────────────────────────
    def get_shipping_address(self, obj):
        """Return a structured address object matching the frontend ShippingAddress type.
        Prefers the related ShippingAddress FK for structured fields; falls back to
        the flat snapshot fields on the Order itself."""
        sa = obj.shipping_address  # FK, may be None
        if sa:
            # Split shipping_full_name on first space for first/last
            parts = sa.shipping_full_name.split(' ', 1)
            return {
                'first_name': parts[0],
                'last_name': parts[1] if len(parts) > 1 else '',
                'email': sa.shipping_email,
                'phone': '',
                'address_line1': sa.shipping_address1,
                'address_line2': sa.shipping_address2 or '',
                'city': sa.shipping_city,
                'region': sa.shipping_state or '',
                'postal_code': sa.shipping_postal_code or '',
                'country': sa.shipping_country,
            }
        # Fallback: reconstruct from flat order snapshot
        parts = obj.full_name.split(' ', 1)
        return {
            'first_name': parts[0],
            'last_name': parts[1] if len(parts) > 1 else '',
            'email': obj.email,
            'phone': '',
            'address_line1': obj.shipping_address_text,
            'address_line2': '',
            'city': '',
            'region': '',
            'postal_code': '',
            'country': '',
        }

    # ── G6 ────────────────────────────────────────────────────────────────
    def get_payment_reference(self, obj):
        return str(obj.invoice_number)

    # ── G7 ────────────────────────────────────────────────────────────────
    STATUS_MAP = {
        'Pending': 'pending',
        'Processing': 'paid',
        'Shipped': 'shipped',
        'Delivered': 'delivered',
        'Cancelled': 'cancelled',
    }

    def get_status(self, obj):
        return self.STATUS_MAP.get(obj.status, obj.status.lower())


class ShippingAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingAddress
        fields = [
            'id', 'shipping_full_name', 'shipping_email',
            'shipping_address1', 'shipping_address2', 'shipping_city',
            'shipping_state', 'shipping_postal_code', 'shipping_country',
        ]
