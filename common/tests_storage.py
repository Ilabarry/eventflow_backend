"""Tests du backend de stockage S3 (common/storage/s3.py).

Aucun appel réseau : les requêtes HTTP sont simulées.
"""

from unittest import mock

from django.core.files.base import ContentFile
from django.test import SimpleTestCase, override_settings

from common.storage.s3 import S3Storage

S3_SETTINGS = dict(
    AWS_STORAGE_BUCKET_NAME="media-bucket",
    AWS_S3_ENDPOINT_URL="https://project.supabase.co/storage/v1/s3",
    AWS_ACCESS_KEY_ID="AKIAEXAMPLE",
    AWS_SECRET_ACCESS_KEY="secret-key",
    AWS_S3_REGION_NAME="eu-central-1",
    AWS_S3_PUBLIC_URL="",
    AWS_S3_QUERYSTRING_EXPIRE=3600,
)


class S3StorageConfigurationTests(SimpleTestCase):
    def test_missing_configuration_is_rejected(self):
        with override_settings(
            AWS_STORAGE_BUCKET_NAME="",
            AWS_S3_ENDPOINT_URL="",
            AWS_ACCESS_KEY_ID="",
            AWS_SECRET_ACCESS_KEY="",
        ):
            with self.assertRaises(ValueError):
                S3Storage()

    def test_invalid_endpoint_is_rejected(self):
        with override_settings(
            **{**S3_SETTINGS, "AWS_S3_ENDPOINT_URL": "pas-une-url"}
        ):
            with self.assertRaises(ValueError):
                S3Storage()

    @override_settings(**S3_SETTINGS)
    def test_object_path_and_signed_url(self):
        storage = S3Storage()

        self.assertEqual(
            storage._object_path("events/covers/a b.jpg"),
            "/storage/v1/s3/media-bucket/events/covers/a%20b.jpg",
        )

        url = storage.url("events/covers/a b.jpg")
        self.assertIn("X-Amz-Algorithm=AWS4-HMAC-SHA256", url)
        self.assertIn("X-Amz-Signature=", url)
        self.assertIn("a%20b.jpg", url)

    @override_settings(
        **{
            **S3_SETTINGS,
            "AWS_S3_PUBLIC_URL": "https://pub-example.r2.dev",
        }
    )
    def test_public_url_is_used_when_configured(self):
        storage = S3Storage()
        self.assertEqual(
            storage.url("events/covers/a b.png"),
            "https://pub-example.r2.dev/events/covers/a%20b.png",
        )


class S3StorageOperationsTests(SimpleTestCase):
    def setUp(self):
        with override_settings(**S3_SETTINGS):
            self.storage = S3Storage()

    def _fake_response(self, *, body=b"", headers=None):
        response = mock.MagicMock()
        response.read.return_value = body
        response.headers = headers or {}
        return response

    def test_save_sends_put_with_guessed_content_type(self):
        fake = self._fake_response()
        with mock.patch.object(self.storage, "_request", return_value=fake) as req:
            name = self.storage._save(
                "events/covers/x.png", ContentFile(b"abc")
            )

        self.assertEqual(name, "events/covers/x.png")
        req.assert_called_once_with(
            "PUT",
            "events/covers/x.png",
            body=b"abc",
            content_type="image/png",
        )
        fake.close.assert_called_once()

    def test_open_returns_file_content(self):
        fake = self._fake_response(body=b"pdf-bytes")
        with mock.patch.object(self.storage, "_request", return_value=fake):
            content = self.storage._open("certificates/x.pdf").read()

        self.assertEqual(content, b"pdf-bytes")

    def test_exists_true_and_false(self):
        with mock.patch.object(
            self.storage, "_request", return_value=self._fake_response()
        ):
            self.assertTrue(self.storage.exists("events/covers/x.png"))

        with mock.patch.object(
            self.storage,
            "_request",
            side_effect=OSError("Erreur stockage S3 (HEAD x) : HTTP 404 "),
        ):
            self.assertFalse(self.storage.exists("events/covers/x.png"))

    def test_delete_ignores_missing_file(self):
        with mock.patch.object(
            self.storage,
            "_request",
            side_effect=OSError("Erreur stockage S3 (DELETE x) : HTTP 404 "),
        ):
            self.storage.delete("events/covers/x.png")  # ne lève pas

    def test_size_reads_content_length(self):
        fake = self._fake_response(headers={"Content-Length": "42"})
        with mock.patch.object(self.storage, "_request", return_value=fake):
            self.assertEqual(self.storage.size("certificates/x.pdf"), 42)
