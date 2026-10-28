"""Fail closed when a build would resolve dependencies without committed lockfiles."""
import argparse
import re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--python", action="store_true")
parser.add_argument("--flutter", action="store_true")
parser.add_argument("--ci", action="store_true")
args = parser.parse_args()
if not (args.python or args.flutter or args.ci):
    parser.error("choose at least one lockfile")

if args.python:
    text = (root / "requirements-dev.txt").read_text()
    if "Generated lockfile will replace" in text:
        raise SystemExit("Python dependency lock has not been generated")
    pins = re.findall(r"(?m)^[A-Za-z0-9_.-]+==[0-9][^\s\\]*", text)
    hashes = text.count("--hash=sha256:")
    if len(pins) < 3 or hashes < len(pins):
        raise SystemExit("Python lockfile must pin transitive dependencies and SHA-256 hashes")
    print(f"Python dependency lock: {len(pins)} packages, {hashes} hashes")

if args.flutter:
    file = root / "apps/mobile_flutter/pubspec.lock"
    if not file.is_file() or "packages:" not in file.read_text():
        raise SystemExit("Flutter pubspec.lock missing; generate with pinned Flutter SDK")
    print("Flutter package lock exists")

if args.ci:
    ci = (root / "requirements-ci.txt").read_text()
    if "Placeholder:" in ci:
        raise SystemExit("CI tool lockfile has not been generated")
    pins = re.findall(r"(?m)^[A-Za-z0-9_.-]+==[0-9][^\\s\\\\]*", ci)
    hashes = ci.count("--hash=sha256:")
    if len(pins) < 8 or hashes < len(pins):
        raise SystemExit("CI toolchain must pin transitive dependencies with hashes")
    print(f"CI toolchain lock: {len(pins)} packages and {hashes} hashes")
