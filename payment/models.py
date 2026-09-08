from django.db import models
from django.contrib.auth.models import User
from store.models import Product
import uuid


class ShippingAddress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    shipping_full_name = models.CharField(max_length=255)
    shipping_email = models.CharField(max_length=255)
    shipping_address1 = models.CharField(max_length=255)
    shipping_address2 = models.CharField(max_length=255, blank=True)
    shipping_city = models.CharField(max_length=100)
    shipping_state = models.CharField(max_length=100, blank=True)
    shipping_postal_code = models.CharField(max_length=20, blank=True)
    shipping_country = models.CharField(max_length=100)


    # don't pluralize address
    class Meta:
        verbose_name_plural = "Shipping Address"
    
    def __str__(self):
        return f"Shipping Address - {str(self.id)}"


class Order(models.Model):
    STATUS_PENDING = 'Pending'
    STATUS_PROCESSING = 'Processing'
    STATUS_SHIPPED = 'Shipped'
    STATUS_DELIVERED = 'Delivered'
    STATUS_CANCELLED = 'Cancelled'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_SHIPPED, 'Shipped'),
        (STATUS_DELIVERED, 'Delivered'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    shipping_address = models.ForeignKey(ShippingAddress, on_delete=models.SET_NULL, null=True, blank=True)

    # Snapshot of shipping info at time of order
    full_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    shipping_address_text = models.TextField(blank=True)

    # Payment & financial
    amount_paid = models.DecimalField(decimal_places=2, max_digits=10, default=0)
    is_paid = models.BooleanField(default=False)

    # Order metadata
    invoice_number = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    date_ordered = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    class Meta:
        ordering = ['-date_ordered']

    def __str__(self):
        return f"Order #{self.invoice_number} — {self.full_name} ({self.status})"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    # Snapshot of price at purchase time
    price = models.DecimalField(decimal_places=2, max_digits=10)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.quantity}x {self.product.name} (Order #{self.order.id})"

    def get_total(self):
        return self.price * self.quantity
