from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User


class UpdateInfoViewTests(TestCase):
    def test_update_info_renders_for_user_without_profile(self):
        user = User.objects.create_user(username='tester', password='StrongPass123')
        self.client.force_login(user)

        response = self.client.get(reverse('update_info'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'User profile')
