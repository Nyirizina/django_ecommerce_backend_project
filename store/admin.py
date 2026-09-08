from django.contrib import admin
from django.utils.html import format_html
from .models import Product, Category, Customer, Order, Profile
from django.contrib.auth.models import User


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'is_sale', 'sale_price', 'stock_badge', 'is_active')
    list_filter = ('category', 'is_sale', 'is_active')
    search_fields = ('name', 'description')
    list_editable = ('is_active', 'is_sale')

    def stock_badge(self, obj):
        if obj.stock == 0:
            return format_html('<span style="color:white;background:#dc3545;padding:2px 8px;border-radius:4px;">Out of Stock</span>')
        elif obj.stock <= 3:
            return format_html('<span style="color:black;background:#ffc107;padding:2px 8px;border-radius:4px;">{} left</span>', obj.stock)
        return format_html('<span style="color:white;background:#198754;padding:2px 8px;border-radius:4px;">{}</span>', obj.stock)
    stock_badge.short_description = 'Stock'


admin.site.register(Category)
admin.site.register(Customer)
admin.site.register(Order)
admin.site.register(Profile)

# mix profile info with user info
class ProfileInline(admin.StackedInline):
    model = Profile

# extend user model
class UserAdmin(admin.ModelAdmin):
    model = User
    fields = ["username", "first_name", "last_name", "email"]
    inlines = [ProfileInline]

# unregister the previous user details in the admin page
admin.site.unregister(User)

#Re-register new userdetails
admin.site.register(User, UserAdmin)