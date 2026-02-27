# apps/accounts/tests.py

from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model

User = get_user_model()


class UserCRUDTests(APITestCase):

    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@test.com",
            password="12345678",
            role="admin",
            is_verified=True,
        )

        self.client.force_authenticate(user=self.admin)

    def test_list_users(self):
        response = self.client.get("/api/users/")
        self.assertEqual(response.status_code, 200)

    def test_update_user(self):
        user = User.objects.create_user(
            username="user1", email="user1@test.com", password="12345678"
        )

        response = self.client.patch(
            f"/api/users/{user.id}/", {"role": "staff"}, format="json"
        )

        self.assertEqual(response.status_code, 200)

    def test_delete_user(self):
        user = User.objects.create_user(
            username="user2", email="user2@test.com", password="12345678"
        )

        response = self.client.delete(f"/api/users/{user.id}/")
        self.assertEqual(response.status_code, 204)
