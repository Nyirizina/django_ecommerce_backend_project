from django.urls import path
from .api_views import ProductListAPIView, ProductDetailAPIView, CategoryListAPIView

urlpatterns = [
    path('products/', ProductListAPIView.as_view(), name='api-products'),
    path('products/<int:pk>/', ProductDetailAPIView.as_view(), name='api-product-detail'),
    path('categories/', CategoryListAPIView.as_view(), name='api-categories'),
]
