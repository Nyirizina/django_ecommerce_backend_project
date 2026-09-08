from django.contrib import admin
from .models import ShippingAddress, Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'price', 'quantity', 'get_total')

    def get_total(self, obj):
        return f"${obj.get_total()}"
    get_total.short_description = 'Line Total'


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    model = Order
    list_display = ('invoice_short', 'full_name', 'email', 'amount_paid', 'status', 'is_paid', 'date_ordered')
    list_filter = ('status', 'is_paid', 'date_ordered')
    search_fields = ('full_name', 'email', 'invoice_number')
    readonly_fields = ('invoice_number', 'date_ordered', 'amount_paid')
    inlines = [OrderItemInline]
    actions = ['mark_shipped', 'mark_delivered', 'mark_processing']

    def invoice_short(self, obj):
        return str(obj.invoice_number)[:13] + '...'
    invoice_short.short_description = 'Invoice #'

    @admin.action(description='Mark selected orders as Shipped')
    def mark_shipped(self, request, queryset):
        updated = queryset.update(status=Order.STATUS_SHIPPED)
        self.message_user(request, f"{updated} order(s) marked as Shipped.")

    @admin.action(description='Mark selected orders as Delivered')
    def mark_delivered(self, request, queryset):
        updated = queryset.update(status=Order.STATUS_DELIVERED)
        self.message_user(request, f"{updated} order(s) marked as Delivered.")

    @admin.action(description='Mark selected orders as Processing')
    def mark_processing(self, request, queryset):
        updated = queryset.update(status=Order.STATUS_PROCESSING)
        self.message_user(request, f"{updated} order(s) marked as Processing.")


admin.site.register(ShippingAddress)
