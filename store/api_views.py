from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny
from django.db.models import Q
from .models import Product, Category
from .serializers import ProductSerializer, CategorySerializer


class ProductListAPIView(ListAPIView):
    serializer_class = ProductSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = Product.objects.filter(is_active=True).select_related('category')
        category = self.request.query_params.get('category')
        # Support both 'search' (frontend convention) and 'q' (legacy)
        search = self.request.query_params.get('search') or self.request.query_params.get('q')
        featured = self.request.query_params.get('featured')
        if category:
            qs = qs.filter(
                Q(category__name__iexact=category) | Q(category__name__iexact=category.replace('-', ' '))
            )
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search))
        if featured == 'true':
            qs = qs.filter(is_featured=True)
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx


class ProductDetailAPIView(RetrieveAPIView):
    queryset = Product.objects.filter(is_active=True).select_related('category')
    serializer_class = ProductSerializer
    permission_classes = [AllowAny]
    # Support lookup by slug (frontend calls /api/products/{slug}/)
    lookup_field = 'slug'

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx


class CategoryListAPIView(ListAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
