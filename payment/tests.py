from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from store.models import Product, Category
from .models import Order, OrderItem, ShippingAddress


class CheckoutIntegrationTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='buyer', password='BuyerPass123')
        self.category = Category.objects.create(name='Shirts')
        self.product = Product.objects.create(
            name='Integration Shirt',
            price='39.99',
            category=self.category,
            stock=10,
        )

    def test_empty_cart_redirects_from_checkout(self):
        """Accessing checkout with an empty cart should redirect to cart summary."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('checkout'))
        self.assertRedirects(response, reverse('cart_summary'))

    def test_checkout_page_renders_with_items(self):
        """Checkout renders correctly when cart has items."""
        self.client.force_login(self.user)
        # Add item to session cart
        session = self.client.session
        session['session_key'] = {str(self.product.id): 2}
        session.save()

        response = self.client.get(reverse('checkout'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Integration Shirt')

    def _add_to_cart(self, product_id, qty):
        session = self.client.session
        session['session_key'] = {str(product_id): qty}
        session.save()

    def _post_shipping(self):
        return self.client.post(reverse('billing_info'), {
            'shipping_full_name': 'Test Buyer',
            'shipping_email': 'buyer@test.com',
            'shipping_address1': '123 Main St',
            'shipping_address2': '',
            'shipping_city': 'Test City',
            'shipping_state': 'TC',
            'shipping_postal_code': '12345',
            'shipping_country': 'Testland',
        })

    def test_full_order_creation_flow(self):
        """Complete checkout creates Order, OrderItems, deducts stock, clears cart."""
        self.client.force_login(self.user)
        self._add_to_cart(self.product.id, 3)

        # Step 1: Submit shipping info
        response = self._post_shipping()
        self.assertEqual(response.status_code, 200)  # renders billing_info.html

        # Step 2: Submit payment / place order
        response = self.client.post(reverse('process_order'))
        self.assertRedirects(response, reverse('payment_success'))

        # Verify Order was created
        self.assertEqual(Order.objects.count(), 1)
        order = Order.objects.first()
        self.assertEqual(order.full_name, 'Test Buyer')
        self.assertEqual(order.status, Order.STATUS_PROCESSING)
        self.assertTrue(order.is_paid)

        # Verify OrderItems
        self.assertEqual(order.items.count(), 1)
        item = order.items.first()
        self.assertEqual(item.product, self.product)
        self.assertEqual(item.quantity, 3)

        # Verify stock deducted
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 7)  # 10 - 3

        # Verify session cart cleared
        self.assertEqual(self.client.session.get('session_key', {}), {})

    def test_orders_requires_login(self):
        response = self.client.get(reverse('orders'))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('orders')}")

    def test_orders_list_shows_user_orders(self):
        self.client.force_login(self.user)
        # Create an order directly
        shipping = ShippingAddress.objects.create(
            user=self.user,
            shipping_full_name='Test Buyer',
            shipping_email='buyer@test.com',
            shipping_address1='123 Main St',
            shipping_city='Test City',
            shipping_country='Testland',
        )
        Order.objects.create(
            user=self.user,
            full_name='Test Buyer',
            email='buyer@test.com',
            shipping_address=shipping,
            amount_paid='39.99',
            is_paid=True,
        )
        response = self.client.get(reverse('orders'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['orders'].count(), 1)
