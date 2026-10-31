import secrets

from django.db import IntegrityError
from django.test import TestCase

from service.models import Account


class AccountStorageTests(TestCase):
    def test_password_is_hashed_and_role_is_server_default(self):
        password = secrets.token_urlsafe(24)
        account = Account.objects.create_user(
            email=" User@Example.COM ",
            password=password,
            display_name="Local User",
        )
        self.assertEqual(account.email, "user@example.com")
        self.assertNotEqual(account.password, password)
        self.assertTrue(account.check_password(password))
        self.assertEqual(account.role, Account.Role.VIEWER)

    def test_case_variant_email_cannot_create_second_account(self):
        Account.objects.create_user(
            email="user@example.com", password=secrets.token_urlsafe(24), display_name="One"
        )
        with self.assertRaises(IntegrityError):
            Account.objects.create_user(
                email="USER@example.com", password=secrets.token_urlsafe(24), display_name="Two"
            )

    def test_short_password_is_rejected(self):
        with self.assertRaises(Exception):
            Account.objects.create_user(
                email="user@example.com", password="short", display_name="User"
            )
        self.assertEqual(Account.objects.count(), 0)

    def test_privileged_creation_is_closed(self):
        with self.assertRaises(RuntimeError):
            Account.objects.create_superuser(
                email="admin@example.com", password=secrets.token_urlsafe(24)
            )

    def test_account_creation_cannot_assign_privileged_role(self):
        with self.assertRaises(TypeError):
            Account.objects.create_user(
                email="user@example.com",
                password=secrets.token_urlsafe(24),
                display_name="User",
                role=Account.Role.ADMINISTRATOR,
            )
