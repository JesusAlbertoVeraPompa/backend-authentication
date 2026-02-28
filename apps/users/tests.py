# apps/accounts/tests.py

from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from rest_framework import status

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

class UserAuditTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="test", email="test@email.com", password="123456")
        self.client.force_authenticate(user=self.user)

    def test_update_my_data_creates_snapshot(self):
        response = self.client.patch("/api/users/me/", {"username": "nuevo_nombre"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Comprobar snapshot
        from apps.users.models_deleted import DeletedUser
        self.assertTrue(DeletedUser.objects.filter(username="test").exists())
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "nuevo_nombre")

    def test_soft_delete_and_restore(self):
        from apps.users.models_deleted import DeletedUser

        # Soft delete
        response = self.client.delete("/api/users/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(User.objects.filter(id=self.user.id).exists())

        deleted_user = DeletedUser.objects.first()
        self.assertIsNotNone(deleted_user)

        # Restaurar
        response = self.client.post("/api/users/restore/", {"email": self.user.email})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email=self.user.email).exists())