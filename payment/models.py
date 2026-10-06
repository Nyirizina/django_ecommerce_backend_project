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


class MoMoPayment(models.Model):
    """
    Tracks a single MTN MoMo Collection Widget payment attempt.

    Security note: `status` is the value reported by the browser widget.
    It is NOT proof of payment. The `verified` field indicates whether
    server-side verification against the MoMo Collection API has confirmed
    the payment. Never trust `status` alone for order fulfilment.
    """
    STATUS_CREATED  = 'created'
    STATUS_PENDING  = 'pending_verification'
    STATUS_SUCCESS  = 'successful'
    STATUS_FAILED   = 'failed'
    STATUS_CANCELED = 'canceled'

    STATUS_CHOICES = [
        (STATUS_CREATED,  'Created'),
        (STATUS_PENDING,  'Pending Verification'),
        (STATUS_SUCCESS,  'Successful'),
        (STATUS_FAILED,   'Failed'),
        (STATUS_CANCELED, 'Canceled'),
    ]

    external_id = models.CharField(
        max_length=100, unique=True, db_index=True,
        help_text='Unique order reference passed to the MoMo widget as data-external-id.',
    )
    amount   = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='EUR')

    # Widget-reported status (client-side — not trusted for fulfilment)
    status = models.CharField(
        max_length=30, choices=STATUS_CHOICES, default=STATUS_CREATED,
    )
    # Invoice / transaction ID reported by the widget event
    invoice_id = models.CharField(max_length=200, blank=True)

    # Server-side verification flag — only True after MoMo API confirms payment
    verified = models.BooleanField(default=False)

    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'MoMo Payment'
        verbose_name_plural = 'MoMo Payments'

    def __str__(self):
        return f"MoMo {self.external_id} [{self.status}]"
