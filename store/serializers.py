from rest_framework import serializers
from .models import Product, Category


class CategorySerializer(serializers.ModelSerializer):
    # Expose a slug derived from the name (Category has no slug field, so we
    # derive it at serialisation time to match the frontend Category type).
    slug = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug']

    def get_slug(self, obj):
        from django.utils.text import slugify
        return slugify(obj.name)


class ProductSerializer(serializers.ModelSerializer):
    category = serializers.CharField(source='category.name', read_only=True)
    category_slug = serializers.SerializerMethodField()
    # Alias: compare_at_price maps to sale_price (frontend convention)
    compare_at_price = serializers.DecimalField(
        source='sale_price', max_digits=10, decimal_places=2, read_only=True
    )
    # Return images as an array of one URL to match frontend Product.images[]
    images = serializers.SerializerMethodField()
    # Expose effective (active) price as a float for the frontend
    price = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'description',
            'price', 'compare_at_price',
            'category', 'category_slug',
            'images', 'sizes', 'colors',
            'stock', 'is_active', 'is_featured',
        ]

    def get_price(self, obj):
        return float(obj.sale_price if obj.is_sale else obj.price)

    def get_category_slug(self, obj):
        from django.utils.text import slugify
        return slugify(obj.category.name)

    def get_images(self, obj):
        request = self.context.get('request')
        if obj.image and request:
            return [request.build_absolute_uri(obj.image.url)]
        return []
