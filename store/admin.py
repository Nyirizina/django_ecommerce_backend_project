from django.contrib import admin
from . models import Product, Category, Customer, Order, Profile
from django.contrib.auth.models import User

admin.site.register(Product)
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
    field = ["username", "first_name", "last_name", "email"]
    inlines = [ProfileInline]

# unregister the previous user details in the admin page
admin.site.unregister(User)

#Re-register new userdetails
admin.site.register(User, UserAdmin)