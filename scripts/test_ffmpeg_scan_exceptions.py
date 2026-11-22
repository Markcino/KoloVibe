"""The FFmpeg scanner exceptions: evidence, `.grype.yaml`, the build recipe and the CI binary check stay in agreement."""
import contextlib
import copy
import datetime
import io
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_ffmpeg_scan_exceptions as checker  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = json.loads((ROOT / "infra/docker/ffmpeg/scan-exceptions.json").read_text())
GRYPE_TEXT = (ROOT / ".grype.yaml").read_text()
GRYPE = yaml.safe_load(GRYPE_TEXT)
APKBUILD = (ROOT / "infra/docker/ffmpeg/APKBUILD").read_text()
CONFIGURE = APKBUILD[APKBUILD.index("./configure"):APKBUILD.index("make -j")]
APPROVED_FIRST = "CVE-2026-107696"
PACKAGE = {"name": "ffmpeg", "version": "9.0.2-r0", "type": "apk"}

VERSION = ("ffmpeg version 9.0.2 Copyright (c) 2000-2026 the FFmpeg developers\n"
           "  built with gcc 15.2.0 (Alpine 15.2.0)\n"
           "  configuration: --prefix=/usr --disable-everything --disable-autodetect --disable-network --disable-doc "
           "--disable-hwaccels --disable-vdpau --enable-gpl --enable-libx264 --enable-decoder=h264 --enable-encoder=aac\n"
           "  libavutil      60.  8.100 / 60.  8.100\n")
DECODERS = (
    "Decoders:\n V..... = Video\n A..... = Audio\n ------\n V....D h264                H.264 / AVC\n"
    " A....D aac                 AAC (Advanced Audio Coding)\n A....D pcm_s16le          PCM signed 16-bit little-endian\n")
ENCODERS = (
    "Encoders:\n V..... = Video\n ------\n V....D libx264            libx264 H.264\n A....D aac                 AAC\n"
    " V....D mjpeg               MJPEG\n A....D pcm_s16le          PCM signed 16-bit little-endian\n")
HWACCELS = "Hardware acceleration methods:\n"
BSFS = "Bitstream filters:\nnull\naac_adtstoasc\n"
LISTINGS = {"decoders": DECODERS, "encoders": ENCODERS, "hwaccels": HWACCELS, "bsfs": BSFS}


class EvidenceMatchesTheScannerConfigTests(unittest.TestCase):
    def test_the_ignore_list_is_the_approved_first_rule_plus_exactly_the_evidenced_cves(self):
        self.assertEqual(set(GRYPE), {"ignore"})
        rules = GRYPE["ignore"]
        expected = [{"vulnerability": APPROVED_FIRST, "package": PACKAGE}] + [
            {"vulnerability": row["cve"], "package": PACKAGE} for row in EVIDENCE["rows"]]
        self.assertEqual(rules[:len(expected)], expected)
        openssl_cves = ("CVE-2026-124709", "CVE-2026-107494", "CVE-2026-121482",
                        "CVE-2026-84786", "CVE-2026-107493")
        openssl = [
            {"vulnerability": cve,
             "package": {"name": name, "version": "3.5.9-r1", "type": "apk"}}
            for cve in openssl_cves for name in ("libssl3", "libcrypto3")
        ]
        self.assertEqual(rules[len(expected):], openssl)
        expiry = datetime.date.fromisoformat(
            re.search(r"(?m)^# Expires \(OpenSSL temporary\): (\d{4}-\d{2}-\d{2})$", GRYPE_TEXT).group(1))
        self.assertEqual(expiry, datetime.date(2026, 11, 28))
        self.assertGreater(expiry, datetime.datetime.now(datetime.timezone.utc).date())
        cves = [row["cve"] for row in EVIDENCE["rows"]]
        self.assertEqual(len(cves), len(set(cves)))
        self.assertNotIn(APPROVED_FIRST, cves)
        for cve in cves:
            self.assertRegex(cve, r"^CVE-2026-\d{5,6}$")

    def test_the_rules_are_scoped_to_one_package_at_one_exact_version(self):
        self.assertEqual(EVIDENCE["package"], PACKAGE)
        for rule in GRYPE["ignore"][:1 + len(EVIDENCE["rows"])]:
            self.assertEqual(set(rule), {"vulnerability", "package"})  # no wildcard, fix-state or path rule
            self.assertEqual(rule["package"], PACKAGE)

    def test_the_second_set_expires_and_the_config_comment_names_the_same_date(self):
        expiry = datetime.date.fromisoformat(EVIDENCE["expires"])
        self.assertGreater(expiry, datetime.date.today(), "the FFmpeg 19 November exceptions expired: re-triage or remove")
        self.assertLessEqual(expiry, datetime.date(2027, 1, 31))
        stated = re.search(r"(?m)^# Expires \(second set\): (\d{4}-\d{2}-\d{2})$", GRYPE_TEXT)
        self.assertIsNotNone(stated)
        self.assertEqual(stated.group(1), EVIDENCE["expires"])

    def test_every_row_names_its_component_and_a_check_a_build_can_fail(self):
        for row in EVIDENCE["rows"]:
            with self.subTest(row["cve"]):
                self.assertTrue(row["component"].strip())
                self.assertTrue(row["absent"] or row["configure_lacks"], "a row with no check proves nothing")
                self.assertTrue(set(row["absent"]) <= set(checker.KINDS))
                for names in row["absent"].values():
                    self.assertTrue(names and all(re.fullmatch(r"[a-z0-9_]+", n) for n in names))
                for option in row["configure_lacks"]:
                    self.assertRegex(option, r"^--enable-[a-z0-9-]+$")


class EvidenceMatchesTheBuildRecipeTests(unittest.TestCase):
    def test_the_build_is_minimal_by_construction(self):
        for option in EVIDENCE["build_must_have"]:
            self.assertIn(option, CONFIGURE)
        for blanket in ("--enable-decoders", "--enable-encoders", "--enable-hwaccels", "--enable-bsfs", "--enable-filters",
                        "--enable-parsers", "--enable-demuxers", "--enable-muxers", "--enable-protocols", "--enable-network",
                        "--enable-autodetect"):
            self.assertNotIn(blanket + " ", CONFIGURE + " ")
        # The exceptions assume a little-endian 64-bit target (several findings apply only to big-endian or 32-bit builds).
        self.assertRegex(APKBUILD, r'(?m)^arch="x86_64 aarch64"$')

    def test_the_enabled_codecs_are_exactly_the_ones_the_exceptions_were_argued_against(self):
        self.assertEqual(sorted(re.findall(r"--enable-decoder=(\w+)", CONFIGURE)),
                         ["aac", "alac", "h264", "hevc", "mp3float", "pcm_s16be", "pcm_s16le", "pcm_s24le"])
        self.assertEqual(sorted(re.findall(r"--enable-encoder=(\w+)", CONFIGURE)), ["aac", "libx264", "mjpeg", "pcm_s16le"])
        self.assertEqual(re.findall(r"--enable-demuxer=(\w+)", CONFIGURE), ["mov"])
        self.assertEqual(re.findall(r"--enable-muxer=(\w+)", CONFIGURE), ["mp4", "image2", "wav"])
        self.assertEqual(re.findall(r"--enable-bsf=(\w+)", CONFIGURE), ["null", "aac_adtstoasc"])

    def test_no_excepted_component_is_enabled_by_the_recipe(self):
        flags = set(re.findall(r"--[a-z0-9-]+(?:=[\w]+)?", CONFIGURE))
        for row in EVIDENCE["rows"]:
            with self.subTest(row["cve"]):
                for option in row["configure_lacks"]:
                    self.assertNotIn(option, flags)
                for kind, names in row["absent"].items():
                    singular = {"decoders": "decoder", "encoders": "encoder", "bsfs": "bsf"}.get(kind)
                    for name in names:
                        if singular:
                            self.assertNotIn("--enable-%s=%s" % (singular, name), flags)
                        self.assertNotIn("--enable-" + name, flags)


class CheckerTests(unittest.TestCase):
    def problems(self, version=VERSION, **overrides):
        return checker.check(EVIDENCE, version, dict(LISTINGS, **overrides))

    def test_a_minimal_binary_satisfies_every_exception(self):
        self.assertEqual(self.problems(), [])

    def test_listing_parsers_read_names_not_legends(self):
        self.assertEqual(checker.listed_names("decoders", DECODERS), {"h264", "aac", "pcm_s16le"})
        self.assertEqual(checker.listed_names("encoders", ENCODERS), {"libx264", "aac", "mjpeg", "pcm_s16le"})
        self.assertEqual(checker.listed_names("hwaccels", HWACCELS), set())
        self.assertEqual(checker.listed_names("bsfs", BSFS), {"null", "aac_adtstoasc"})
        with self.assertRaises(ValueError):
            checker.listed_names("decoders", "nonsense")

    def test_vdpau_is_forbidden_even_when_other_hardware_is_disabled(self):
        self.assertEqual(self.problems(), [])
        self.assertTrue(any(
            problem.startswith("CVE-2026-125219")
            for problem in self.problems(hwaccels=HWACCELS + "vdpau\n")
        ))
        self.assertTrue(any(
            "the build lacks --disable-vdpau" in problem
            for problem in self.problems(version=VERSION.replace("--disable-vdpau ", ""))
        ))
        self.assertTrue(any(
            "the build lacks --disable-hwaccels" in problem
            for problem in self.problems(version=VERSION.replace("--disable-hwaccels ", ""))
        ))

    def test_an_enabled_excepted_component_is_reported_by_cve(self):
        cases = [
            ("decoders", DECODERS + " V....D flic                FLI/FLC/FLX video\n", "CVE-2026-125181"),
            ("decoders", DECODERS + " V....D huffyuv            Huffyuv\n", "CVE-2026-125229"),
            ("decoders", DECODERS + " V....D vvc                 H.266 / VVC\n", "CVE-2026-125251"),
            ("encoders", ENCODERS + " V....D gif                 GIF\n", "CVE-2026-125250"),
            ("encoders", ENCODERS + " V....D prores_ks           ProRes\n", "CVE-2026-125259"),
            ("hwaccels", HWACCELS + "vaapi\n", "CVE-2026-125202"),
            ("hwaccels", HWACCELS + "vulkan\n", "CVE-2026-125249"),
            ("bsfs", BSFS + "h264_metadata\n", "CVE-2026-125269"),
            ("bsfs", BSFS + "filter_units\n", "CVE-2026-125227"),
        ]
        for kind, listing, cve in cases:
            with self.subTest(kind=kind, cve=cve):
                found = self.problems(**{kind: listing})
                self.assertTrue(any(p.startswith(cve) for p in found), found)

    def test_an_enabled_library_option_is_reported(self):
        for option, cve in (("--enable-libwebp", "CVE-2026-125204"), ("--enable-liblcevc-dec", "CVE-2026-125262"),
                            ("--enable-vaapi", "CVE-2026-125202"), ("--enable-libaribcaption", "CVE-2026-125210")):
            with self.subTest(option=option):
                found = self.problems(version=VERSION.replace("--enable-gpl", "--enable-gpl " + option))
                self.assertTrue(any(p.startswith(cve) for p in found), found)

    def test_a_build_that_is_not_minimal_fails_whatever_the_listings_say(self):
        self.assertTrue(self.problems(version=VERSION.replace("--disable-everything ", "")))
        self.assertTrue(self.problems(version=VERSION.replace("--disable-autodetect ", "")))
        self.assertTrue(self.problems(version=VERSION.replace("--enable-gpl", "--enable-gpl --enable-decoders")))
        with self.assertRaises(ValueError):
            self.problems(version="ffmpeg version 9.0.2\n")  # no configuration line at all

    def test_a_row_without_any_check_is_rejected(self):
        broken = copy.deepcopy(EVIDENCE)
        broken["rows"][0]["absent"], broken["rows"][0]["configure_lacks"] = {}, []
        self.assertTrue(any("no check recorded" in p for p in checker.check(broken, VERSION, LISTINGS)))

    def test_an_option_must_match_exactly_not_as_a_prefix(self):
        near = VERSION.replace("--enable-gpl", "--enable-gpl --enable-vaapi-extra")
        self.assertEqual(self.problems(version=near), [])  # a different option is not the excepted one

    def test_main_exits_zero_on_success_and_one_on_a_violation(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            files = {"v": VERSION, "d": DECODERS, "e": ENCODERS, "h": HWACCELS, "b": BSFS}
            for name, content in files.items():
                (base / name).write_text(content)
            args = ["x", str(ROOT / "infra/docker/ffmpeg/scan-exceptions.json")] + [str(base / n) for n in "vdehb"]
            self.assertEqual(checker.main(args), 0)
            (base / "h").write_text(HWACCELS + "vdpau\n")
            # The negative test MUST fail the checker but must not emit a real
            # GitHub Actions ::error:: annotation for a synthetic fixture.
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                self.assertEqual(checker.main(args), 1)
            self.assertIn("CVE-2026-125219: vdpau is present", stdout.getvalue())
            self.assertIn("FFmpeg scan exceptions no longer hold", stderr.getvalue())
        self.assertEqual(checker.main(["x"]), 2)


if __name__ == "__main__":
    unittest.main()
