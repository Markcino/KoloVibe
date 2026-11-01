"""Verified image artifacts must be bound to their bytes and gated commit."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.verify_image_artifact import verify

SHA = "a" * 40
IMAGE_ID = "sha256:" + "b" * 64


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="kolovibe-image-test-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        payload = b"test-only archive bytes"
        (self.directory / "image.tar").write_bytes(payload)
        (self.directory / "image.tar.sha256").write_text(
            hashlib.sha256(payload).hexdigest() + "  image.tar\n")
        (self.directory / "image-id.txt").write_text(IMAGE_ID)
        (self.directory / "revision.txt").write_text(SHA)
        (self.directory / "service.txt").write_text("gateway")
        (self.directory / "image-sbom.json").write_text(json.dumps(
            {"bomFormat": "CycloneDX", "components": []}))

    def test_correct_artifact_has_verified_identity(self):
        self.assertEqual(verify(self.directory, "gateway", SHA), IMAGE_ID)

    def test_mismatched_commit_or_service_cannot_publish(self):
        for service, revision in (("identity", SHA), ("gateway", "c" * 40)):
            with self.assertRaises(ValueError):
                verify(self.directory, service, revision)

    def test_modified_bytes_cannot_publish(self):
        (self.directory / "image.tar").write_bytes(b"unverified replacement")
        with self.assertRaises(ValueError):
            verify(self.directory, "gateway", SHA)

    def test_malformed_checksum_or_identity_cannot_publish(self):
        for filename, value in (("image.tar.sha256", "not-a-checksum  ../other.tar"),
                                ("image-id.txt", "not-an-image-id")):
            original = (self.directory / filename).read_text()
            (self.directory / filename).write_text(value)
            with self.assertRaises(ValueError):
                verify(self.directory, "gateway", SHA)
            (self.directory / filename).write_text(original)

    def test_missing_artifact_or_invalid_sbom_cannot_publish(self):
        (self.directory / "image-sbom.json").write_text("{}")
        with self.assertRaises(ValueError):
            verify(self.directory, "gateway", SHA)
        (self.directory / "image.tar").unlink()
        with self.assertRaises(FileNotFoundError):
            verify(self.directory, "gateway", SHA)


if __name__ == "__main__":
    unittest.main()
