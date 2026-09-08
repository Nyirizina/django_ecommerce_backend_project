import json
from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from django.contrib.sessions.backends.db import SessionStore
from store.models import Product, Category


def make_request_with_session(user=None):
    """Helper: create a request with a real session."""
    factory = RequestFactory()
    request = factory.get('/')
    request.session = SessionStore()
    request.session.create()
    if user:
        request.user = user
    else:
        from django.contrib.auth.models import AnonymousUser
        request.user = AnonymousUser()
    return request


class CartOperationsTest(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Test Category')
        self.product = Product.objects.create(
            name='Test Shirt',
            price='29.99',
            category=self.category,
            stock=10,
        )
        self.product2 = Product.objects.create(
            name='Sale Shirt',
            price='49.99',
            sale_price='24.99',
            is_sale=True,
            category=self.category,
            stock=5,
        )

    def test_add_product_to_cart(self):
        from cart.cart import Cart
        request = make_request_with_session()
        cart = Cart(request)
        cart.add(self.product, 2)
        self.assertIn(str(self.product.id), cart.cart)
        self.assertEqual(cart.cart[str(self.product.id)], 2)

    def test_cart_length(self):
        from cart.cart import Cart
        request = make_request_with_session()
        cart = Cart(request)
        cart.add(self.product, 1)
        cart.add(self.product2, 3)
        self.assertEqual(len(cart), 2)

    def test_update_cart_quantity(self):
        from cart.cart import Cart
        request = make_request_with_session()
        cart = Cart(request)
        cart.add(self.product, 1)
        cart.update(self.product.id, 5)
        self.assertEqual(cart.cart[str(self.product.id)], 5)

    def test_delete_product_from_cart(self):
        from cart.cart import Cart
        request = make_request_with_session()
        cart = Cart(request)
        cart.add(self.product, 2)
        cart.delete(self.product.id)
        self.assertNotIn(str(self.product.id), cart.cart)

    def test_totals_uses_regular_price(self):
        from cart.cart import Cart
        request = make_request_with_session()
        cart = Cart(request)
        cart.add(self.product, 2)
        total = cart.totals()
        self.assertEqual(float(total), 2 * 29.99)

    def test_totals_uses_sale_price(self):
        from cart.cart import Cart
        request = make_request_with_session()
        cart = Cart(request)
        cart.add(self.product2, 3)
        total = cart.totals()
        self.assertAlmostEqual(float(total), 3 * 24.99)

    def test_cart_serializes_to_valid_json(self):
        """Verifies json.dumps fix — cart should serialize without errors."""
        from cart.cart import Cart
        request = make_request_with_session()
        cart = Cart(request)
        cart.add(self.product, 2)
        cart.add(self.product2, 1)
        serialized = json.dumps(cart.cart)
        deserialized = json.loads(serialized)
        self.assertEqual(deserialized[str(self.product.id)], 2)
