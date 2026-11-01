"""Reject mismatched revision, shared-service inventory, image identity or bytes."""

import argparse
import hashlib
import json
from pathlib import Path
import re

SERVICES = ("gateway", "identity", "creators", "content", "engagement", "points",
            "moderation", "audit")


def verify(directory, revision):
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Invalid artifact revision")
    directory = Path(directory)
    if (directory / "revision.txt").read_text().strip() != revision:
        raise ValueError("Artifact belongs to a different commit")
    services = json.loads((directory / "services.json").read_text())
    if services != list(SERVICES):
        raise ValueError("Artifact must contain the complete shared-service inventory")
    image_id = (directory / "image-id.txt").read_text().strip()
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
        raise ValueError("Invalid artifact image identity")
    checksum = (directory / "image.tar.sha256").read_text().strip()
    if not re.fullmatch(r"[0-9a-f]{64}  image\.tar", checksum):
        raise ValueError("Invalid image archive checksum record")
    digest = hashlib.sha256()
    with (directory / "image.tar").open("rb") as archive:
        for chunk in iter(lambda: archive.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != checksum.split()[0]:
        raise ValueError("Verified image archive checksum mismatch")
    sbom = json.loads((directory / "image-sbom.json").read_text())
    if sbom.get("bomFormat") != "CycloneDX" or not isinstance(sbom.get("components"), list):
        raise ValueError("Missing or invalid image CycloneDX SBOM")
    return image_id


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    print(verify(args.directory, args.revision))
