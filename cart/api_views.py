"""
cart/api_views.py
───────────────────────────────────────────────────────────────────────────────
REST API wrapper around the existing session-based Cart class.
No new models needed — the cart lives in the Django session; CORS credentials
let the browser session cookie travel cross-origin from localhost:3000.

Endpoints:
  GET    /api/cart/               → list current cart items
  POST   /api/cart/add/           → add item  {product_id, quantity, size?}
  PATCH  /api/cart/update/<id>/   → update qty {quantity}
  DELETE /api/cart/remove/<id>/   → remove item
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status
from django.shortcuts import get_object_or_404
from cart.cart import Cart
from store.models import Product
from store.serializers import ProductSerializer


def _build_items(cart, request):
    """Convert the Cart session dict into a list of CartItem-shaped dicts."""
    product_ids = list(cart.cart.keys())
    quantities = cart.get_quants()
    products = {
        str(p.id): p
        for p in Product.objects.filter(id__in=product_ids).select_related('category')
    }
    items = []
    for pid_str, qty in quantities.items():
        product = products.get(pid_str)
        if not product:
            continue
        price = float(product.sale_price if product.is_sale else product.price)
        items.append({
            'id': int(pid_str),          # use product id as item id (session cart has no row id)
            'product': ProductSerializer(product, context={'request': request}).data,
            'quantity': qty,
            'size': None,                # session cart doesn't track size; add later if needed
            'line_total': round(price * qty, 2),
        })
    return items


class CartView(APIView):
    """GET /api/cart/ — return the current session cart items."""
    permission_classes = [AllowAny]

    def get(self, request):
        cart = Cart(request)
        return Response(_build_items(cart, request))


class CartAddView(APIView):
    """POST /api/cart/add/ — body: {product_id, quantity, size?}"""
    permission_classes = [AllowAny]

    def post(self, request):
        product_id = request.data.get('product_id')
        quantity = int(request.data.get('quantity', 1))
        if not product_id:
            return Response({'error': 'product_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        product = get_object_or_404(Product, id=product_id, is_active=True)
        cart = Cart(request)
        cart.add(product=product, quantity=quantity)
        # Return the specific line item that was just added/updated
        price = float(product.sale_price if product.is_sale else product.price)
        item = {
            'id': product.id,
            'product': ProductSerializer(product, context={'request': request}).data,
            'quantity': cart.cart.get(str(product.id), quantity),
            'size': request.data.get('size'),
            'line_total': round(price * cart.cart.get(str(product.id), quantity), 2),
        }
        return Response(item, status=status.HTTP_201_CREATED)


class CartUpdateView(APIView):
    """PATCH /api/cart/update/<id>/ — body: {quantity}"""
    permission_classes = [AllowAny]

    def patch(self, request, id):
        quantity = int(request.data.get('quantity', 1))
        product = get_object_or_404(Product, id=id, is_active=True)
        cart = Cart(request)
        if quantity < 1:
            cart.delete(product=id)
            return Response(status=status.HTTP_204_NO_CONTENT)
        cart.update(product=id, quantity=quantity)
        price = float(product.sale_price if product.is_sale else product.price)
        item = {
            'id': id,
            'product': ProductSerializer(product, context={'request': request}).data,
            'quantity': quantity,
            'size': None,
            'line_total': round(price * quantity, 2),
        }
        return Response(item)


class CartRemoveView(APIView):
    """DELETE /api/cart/remove/<id>/"""
    permission_classes = [AllowAny]

    def delete(self, request, id):
        cart = Cart(request)
        cart.delete(product=id)
        return Response(status=status.HTTP_204_NO_CONTENT)
