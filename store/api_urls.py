from django.urls import path
from .api_views import ProductListAPIView, ProductDetailAPIView, CategoryListAPIView

urlpatterns = [
    path('products/', ProductListAPIView.as_view(), name='api-products'),
    # Frontend calls /api/products/{slug}/ — lookup_field='slug' on the view
    path('products/<slug:slug>/', ProductDetailAPIView.as_view(), name='api-product-detail'),
    path('categories/', CategoryListAPIView.as_view(), name='api-categories'),
]
