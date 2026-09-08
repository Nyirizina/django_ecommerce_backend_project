from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from .models import Profile, Product, Category


class ProfileSignalTest(TestCase):
    """Profile is auto-created when a User is saved."""

    def test_profile_created_on_user_save(self):
        user = User.objects.create_user(username='testuser', password='testpass123')
        self.assertTrue(Profile.objects.filter(user=user).exists())

    def test_profile_not_duplicated_on_user_update(self):
        user = User.objects.create_user(username='testuser2', password='testpass123')
        user.first_name = 'Updated'
        user.save()
        self.assertEqual(Profile.objects.filter(user=user).count(), 1)

    def test_get_or_create_safe_for_existing_profile(self):
        """Simulates the get_or_create fix — should not raise DoesNotExist."""
        user = User.objects.create_user(username='testuser3', password='testpass123')
        profile, created = Profile.objects.get_or_create(user=user)
        self.assertFalse(created)  # Already exists from signal
        self.assertEqual(profile.user, user)

    def test_get_or_create_safe_when_no_profile(self):
        """get_or_create should create a profile if one doesn't exist."""
        user = User.objects.create_user(username='testuser4', password='testpass123')
        # Manually delete profile to simulate pre-signal user
        Profile.objects.filter(user=user).delete()
        profile, created = Profile.objects.get_or_create(user=user)
        self.assertTrue(created)


class UserRegistrationTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_register_view_get(self):
        response = self.client.get(reverse('register'))
        self.assertEqual(response.status_code, 200)

    def test_register_creates_user_and_profile(self):
        response = self.client.post(reverse('register'), {
            'username': 'newuser',
            'first_name': 'New',
            'last_name': 'User',
            'email': 'new@test.com',
            'password1': 'SecurePass@123',
            'password2': 'SecurePass@123',
        })
        self.assertTrue(User.objects.filter(username='newuser').exists())
        user = User.objects.get(username='newuser')
        self.assertTrue(Profile.objects.filter(user=user).exists())

    def test_login_view_get(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)

    def test_login_user_success(self):
        User.objects.create_user(username='logintest', password='testpass123')
        response = self.client.post(reverse('login'), {
            'username': 'logintest',
            'password': 'testpass123',
        })
        self.assertRedirects(response, reverse('home'))

    def test_login_invalid_credentials(self):
        response = self.client.post(reverse('login'), {
            'username': 'nobody',
            'password': 'wrongpassword',
        })
        self.assertRedirects(response, reverse('login'))


class ProductModelTest(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='T-shirts')
        self.product = Product.objects.create(
            name='Test Shirt',
            price=29.99,
            category=self.category,
            stock=10,
            is_active=True,
        )

    def test_product_str(self):
        self.assertEqual(str(self.product), 'Test Shirt')

    def test_product_has_stock(self):
        self.assertEqual(self.product.stock, 10)

    def test_product_is_active(self):
        self.assertTrue(self.product.is_active)

