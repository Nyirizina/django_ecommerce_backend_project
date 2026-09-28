from django.urls import path
from .api_views import CartView, CartAddView, CartUpdateView, CartRemoveView

urlpatterns = [
    path('cart/', CartView.as_view(), name='api-cart'),
    path('cart/add/', CartAddView.as_view(), name='api-cart-add'),
    path('cart/update/<int:id>/', CartUpdateView.as_view(), name='api-cart-update'),
    path('cart/remove/<int:id>/', CartRemoveView.as_view(), name='api-cart-remove'),
]
