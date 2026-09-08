from rest_framework import serializers
from .models import Order, OrderItem, ShippingAddress


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_image = serializers.SerializerMethodField()
    line_total = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'product_name', 'product_image', 'price', 'quantity', 'line_total']

    def get_product_image(self, obj):
        request = self.context.get('request')
        if obj.product.image and request:
            return request.build_absolute_uri(obj.product.image.url)
        return None

    def get_line_total(self, obj):
        return str(obj.get_total())


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'invoice_number', 'full_name', 'email',
            'shipping_address_text', 'amount_paid', 'is_paid',
            'status', 'date_ordered', 'items',
        ]


class ShippingAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingAddress
        fields = [
            'id', 'shipping_full_name', 'shipping_email',
            'shipping_address1', 'shipping_address2', 'shipping_city',
            'shipping_state', 'shipping_postal_code', 'shipping_country',
        ]
