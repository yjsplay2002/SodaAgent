import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.user_profile_service import UserProfileService


class UserProfileServiceTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.service = UserProfileService(base_dir=self.temp_dir.name)
        self.user = SimpleNamespace(
            uid="firebase-user-123",
            email="user@example.com",
            display_name="Soda User",
            photo_url="https://example.com/avatar.png",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_get_or_create_profile_persists_auth_fields(self):
        profile = self.service.get_or_create_profile(self.user)

        self.assertEqual(profile.uid, self.user.uid)
        self.assertEqual(profile.email, self.user.email)
        self.assertEqual(profile.display_name, self.user.display_name)

        loaded = self.service.get_profile(self.user.uid)
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded.photo_url, self.user.photo_url)

    def test_update_phone_number_normalizes_and_persists(self):
        profile = self.service.update_phone_number(
            self.user,
            "+82 10-1234-5678",
        )

        self.assertEqual(profile.phone_number, "+821012345678")
        self.assertEqual(
            self.service.get_phone_number(self.user.uid),
            "+821012345678",
        )

    def test_update_phone_number_requires_country_code(self):
        with self.assertRaises(ValueError):
            self.service.update_phone_number(self.user, "010-1234-5678")


if __name__ == "__main__":
    unittest.main()
