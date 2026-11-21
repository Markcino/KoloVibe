import hashlib
from io import StringIO
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from service import media_encoding, screening, screening_providers as providers
from service.media_processing import process
from service.models import Fingerprint, MediaUpload, ScreeningRecord, Video
from service.moderation import _apply
from service.screening import DUPLICATE, ERROR, MUSIC, NSFW, Config, Finding, Media, ProviderResult, decide


class Fake:
    def __init__(self, name, *findings, fingerprints=(), error=False):
        self.name, self.findings, self.fingerprints, self.error = name, findings, list(fingerprints), error

    def screen(self, media):
        if self.error:
            raise RuntimeError("provider down")
        return ProviderResult(list(self.findings), self.fingerprints)


class NoSampling:
    @staticmethod
    def random():
        return 1.0


class AlwaysSample:
    @staticmethod
    def random():
        return 0.0


class DecisionTests(TestCase):
    cfg = Config(enabled=True, screeners=("x",), sample_rate=0.0)

    def decide(self, *findings, config=None, rng=NoSampling):
        return decide(list(findings), 60_000, config or self.cfg, rng)

    def test_clean_video_publishes_and_sampling_sends_a_share_to_humans(self):
        self.assertEqual(self.decide().action, screening.PUBLISH)
        self.assertEqual(self.decide().rights_status, "attested")
        sampled = self.decide(config=Config(enabled=True, sample_rate=0.5), rng=AlwaysSample)
        self.assertEqual((sampled.action, sampled.reason), (screening.REVIEW, "sampled"))

    def test_duplicates_and_explicit_content_are_hidden_for_human_review(self):
        for finding in (Finding("pdq", DUPLICATE, 0.9), Finding("nsfw", NSFW, 0.95)):
            decision = self.decide(finding)
            self.assertEqual((decision.action, decision.rights_status), (screening.HIDE, "hidden"))

    def test_uncertain_scores_and_provider_errors_fail_closed(self):
        for finding in (Finding("nsfw", NSFW, 0.6), Finding("pdq", DUPLICATE, 0.6),
                        Finding("music_id", MUSIC, 0.5), Finding("pdq", ERROR, 1.0)):
            decision = self.decide(finding)
            self.assertEqual((decision.action, decision.rights_status), (screening.REVIEW, "flagged"))

    def test_music_matches_mute_merged_segments_unless_they_dominate(self):
        decision = self.decide(Finding("chromaprint", MUSIC, 0.9, segments=((1000, 5000), (4000, 9000))),
                               Finding("music_id", MUSIC, 1.0, segments=((20_000, 25_000),)))
        self.assertEqual((decision.action, decision.rights_status), (screening.MUTE, "muted"))
        self.assertEqual(decision.mute_segments, ((1000, 9000), (20_000, 25_000)))
        self.assertEqual(self.decide(Finding("music_id", MUSIC, 1.0, segments=((0, 55_000),))).action, screening.HIDE)

    def test_thresholds_are_configurable_and_validated(self):
        strict = Config(enabled=True, nsfw_hide=0.3, nsfw_review=0.2, sample_rate=0.0)
        self.assertEqual(self.decide(Finding("nsfw", NSFW, 0.35), config=strict).action, screening.HIDE)
        self.assertFalse(screening.load_config({}).enabled)
        loaded = screening.load_config({"KOLOVIBE_AUTO_SCREENING": "1", "KOLOVIBE_SCREEN_NSFW_HIDE": "0.7"})
        self.assertEqual((loaded.enabled, loaded.nsfw_hide), (True, 0.7))
        for bad in ({"KOLOVIBE_SCREEN_NSFW_HIDE": "2"}, {"KOLOVIBE_SCREEN_NSFW_HIDE": "x"},
                    {"KOLOVIBE_SCREEN_NSFW_HIDE": "0.1"}, {"KOLOVIBE_SCREENERS": " , "}):
            with self.assertRaises(ValueError):
                screening.load_config({"KOLOVIBE_AUTO_SCREENING": "1"} | bad)

    def test_no_screeners_never_means_clean(self):
        media = Media(uuid4(), uuid4(), Path("a"), Path("b"), 60_000, Path("."))
        outcome = screening.evaluate(media, Config(enabled=True, sample_rate=0.0), screeners=[])
        self.assertEqual(outcome.decision.action, screening.REVIEW)
        self.assertEqual(screening.evaluate(media, Config(enabled=True, screeners=("nope",))).decision.action,
                         screening.REVIEW)


@patch.dict(os.environ, {"KOLOVIBE_AUTO_SCREENING": "1", "KOLOVIBE_SCREEN_SAMPLE_RATE": "0"})
@patch("service.media_encoding.render_poster")
@patch("service.media_storage.put_poster")
@patch("service.media_storage.put_playback")
@patch("service.media_encoding.encode", return_value=20_000)
@patch("service.media_storage.download_upload")
class WorkerScreeningTests(TestCase):
    def setUp(self):
        self.video = Video.objects.create(creator_id=uuid4(), title="Original", state=Video.State.PROCESSING)
        MediaUpload.objects.create(id=uuid4(), video=self.video, expected_bytes=10,
                                   expires_at=timezone.now(), source_etag='"object"')

    def run_worker(self, *screeners):
        with patch("service.screening.providers", return_value=list(screeners)):
            process(self.video.id)
        self.video.refresh_from_db()

    def test_clean_upload_is_published_privately_with_an_automated_approval(self, download, encode, put, poster, render):
        self.run_worker(Fake("pdq", fingerprints=[("pdq", "0" * 64)]))
        self.assertEqual((self.video.state, self.video.visibility, self.video.approval_source),
                         ("published", "private", "automated"))
        self.assertEqual(self.video.rights_status, "attested")
        self.assertIsNotNone(self.video.moderation_approved_at)
        self.assertEqual(list(ScreeningRecord.objects.values_list("provider", "action")), [("decision", "publish")])
        self.assertEqual(Fingerprint.objects.filter(video=self.video, blocked=False).count(), 1)

    def test_music_match_is_muted_before_the_playback_is_stored(self, download, encode, put, poster, render):
        finding = Finding("chromaprint", MUSIC, 0.9, "chromaprint_match", ((2000, 6000),))
        with patch("service.media_encoding.mute_segments") as mute:
            self.run_worker(Fake("chromaprint", finding))
        self.assertEqual(mute.call_args.args[2:], (((2000, 6000),), 20_000))
        self.assertEqual(put.call_args.args[1].name, "muted.mp4")
        self.assertEqual((self.video.state, self.video.rights_status), ("published", "muted"))
        record = ScreeningRecord.objects.get(provider="chromaprint")
        self.assertEqual((record.score, record.segments), (0.9, [[2000, 6000]]))

    def test_failed_mute_holds_the_video_for_a_human(self, download, encode, put, poster, render):
        finding = Finding("music_id", MUSIC, 1.0, "music_id_match", ((0, 4000),))
        with patch("service.media_encoding.mute_segments", side_effect=media_encoding.InvalidMedia):
            self.run_worker(Fake("music_id", finding))
        self.assertEqual((self.video.state, self.video.rights_status, self.video.approval_source),
                         ("review", "flagged", "human"))
        self.assertIsNone(self.video.moderation_approved_at)

    def test_matches_provider_failures_and_bad_configuration_never_auto_publish(self, download, encode, put, poster, render):
        self.run_worker(Fake("nsfw", Finding("nsfw", NSFW, 0.99)))
        self.assertEqual((self.video.state, self.video.rights_status), ("review", "hidden"))
        for screeners in ((Fake("pdq", error=True),), ()):
            Video.objects.filter(pk=self.video.pk).update(state="processing")
            MediaUpload.objects.filter(video=self.video).update(lease_until=None)
            self.run_worker(*screeners)
            self.assertEqual((self.video.state, self.video.rights_status), ("review", "flagged"))
        Video.objects.filter(pk=self.video.pk).update(state="processing")
        MediaUpload.objects.filter(video=self.video).update(lease_until=None)
        with patch.dict(os.environ, {"KOLOVIBE_SCREEN_MUSIC_MUTE": "bad"}):
            process(self.video.id)
        self.video.refresh_from_db()
        self.assertEqual((self.video.state, self.video.rights_status), ("review", "flagged"))
        self.assertEqual(ScreeningRecord.objects.filter(reason="no_screeners").count(), 2)

    def test_screening_is_off_by_default_and_keeps_human_review(self, download, encode, put, poster, render):
        with patch.dict(os.environ, {"KOLOVIBE_AUTO_SCREENING": "0"}):
            self.run_worker(Fake("pdq"))
        self.assertEqual((self.video.state, self.video.rights_status), ("review", "not_recorded"))
        self.assertFalse(ScreeningRecord.objects.exists())


class ProviderTests(TestCase):
    def media(self, directory, creator=None, video=None, content=b"original-bytes"):
        source = Path(directory) / "source.mp4"
        source.write_bytes(content)
        return Media(video or uuid4(), creator or uuid4(), source, source, 60_000, Path(directory))

    def stored(self, kind, value, *, blocked=False, creator=None, state="review"):
        owner = Video.objects.create(creator_id=creator or uuid4(), title="Other", state=state)
        return Fingerprint.objects.create(video=owner, kind=kind, value=value, blocked=blocked)

    def test_exact_hash_matches_blocked_files_and_other_creators_only(self):
        with TemporaryDirectory() as directory:
            media = self.media(directory)
            digest = hashlib.sha256(b"original-bytes").hexdigest()
            self.assertEqual(providers.ExactHashProvider().screen(media).findings, [])
            own = self.stored("sha256", digest, creator=media.creator_id)
            self.assertEqual(providers.ExactHashProvider().screen(media).findings, [])
            own.delete()
            self.stored("sha256", digest)
            self.assertEqual(providers.ExactHashProvider().screen(media).findings[0].reason, "exact_duplicate")
            Fingerprint.objects.update(blocked=True)
            self.assertEqual(providers.ExactHashProvider().screen(media).findings[0].reason, "exact_blocked")

    def test_pdq_scores_median_frame_similarity_against_other_creators(self):
        base = int("ab" * 32, 16)
        self.stored("pdq", f"{base:064x}")
        near = base ^ 0b111  # three bits differ
        with TemporaryDirectory() as directory, patch.object(providers, "_frames", return_value=[1, 2, 3]):
            result = providers.PdqProvider(lambda frames: [near, near, base ^ (2 ** 64 - 1)]).screen(self.media(directory))
            self.assertEqual(len(result.fingerprints), 3)
            self.assertAlmostEqual(result.findings[0].score, 1 - 3 / 64)
            unrelated = providers.PdqProvider(lambda frames: [base ^ (2 ** 128 - 1)]).screen(self.media(directory))
            self.assertEqual(unrelated.findings, [])

    def test_chromaprint_alignment_finds_the_blocked_segment_and_ignores_silence(self):
        import random
        rng = random.Random(7)
        reference = [rng.getrandbits(32) for _ in range(200)]
        noisy = [value ^ (1 << rng.randrange(32)) for value in reference[20:140]]
        candidate = [rng.getrandbits(32) for _ in range(30)] + noisy + [rng.getrandbits(32) for _ in range(30)]
        rate, first, last = providers.align(candidate, reference)
        self.assertLess(rate, 0.05)
        self.assertTrue(30 - 4 <= first <= 30 + 4 and 150 - 4 <= last <= 150 + 4, (first, last))
        self.assertIsNone(providers.align([0] * 200, reference))
        unrelated = providers.align([rng.getrandbits(32) for _ in range(150)], reference)
        self.assertTrue(unrelated is None or unrelated[0] > 0.35)
        self.stored("chromaprint", ",".join(map(str, reference)), blocked=True)
        with TemporaryDirectory() as directory, patch.object(providers, "_audio", return_value=Path("a.wav")):
            media = self.media(directory)
            result = providers.ChromaprintProvider(lambda wav: candidate).screen(media)
            finding = result.findings[0]
            self.assertGreater(finding.score, 0.9)
            (start, end), = finding.segments
            self.assertTrue(abs(start - 30 * 123.8) < 600 and abs(end - 150 * 123.8) < 600, finding.segments)
            with patch.object(providers, "_audio", return_value=None):
                self.assertEqual(providers.ChromaprintProvider().screen(media).findings, [])

    def test_music_id_marks_only_matched_windows_and_nudenet_scores_the_worst_frame(self):
        class Client:
            def identify(self, wav):
                return wav.name in {"music-1.wav", "music-2.wav"}

        with TemporaryDirectory() as directory, patch.object(providers, "_audio", return_value=Path("a.wav")), \
                patch.object(media_encoding, "extract_audio"), patch.object(providers, "_frames", return_value=[1, 2]):
            media = self.media(directory)
            finding = providers.MusicIdProvider(Client()).screen(media).findings[0]
            self.assertEqual(finding.segments, ((12_000, 24_000), (24_000, 36_000)))
            nsfw = providers.NudeNetProvider(lambda frames: [0.1, 0.8]).screen(media)
            self.assertEqual(nsfw.findings[0].score, 0.8)
            self.assertEqual(providers.NudeNetProvider(lambda frames: [0.0]).screen(media).findings, [])

    def test_unknown_provider_names_are_refused(self):
        with self.assertRaises(ValueError):
            providers.build("unknown")


class MuteAndModerationTests(TestCase):
    def test_mute_command_uses_only_validated_numeric_segments(self):
        with TemporaryDirectory() as directory:
            target = Path(directory) / "out.mp4"
            captured = {}

            def fake_run(args, timeout, **kwargs):
                captured["args"] = args
                target.write_bytes(b"x")

            with patch.object(media_encoding, "_run", fake_run), patch.object(media_encoding, "_probe", return_value=20.0):
                media_encoding.mute_segments(Path("in.mp4"), target, [(1000, 2500)], 20_000)
            self.assertIn("volume=enable='between(t,1.000,2.500)':volume=0", captured["args"])
            self.assertIn("copy", captured["args"])
            for bad in ([], [(5, 5)], [(0, 20_001)], [(-1, 5)], [("0", 5)], [(0, 1)] * 21):
                with self.assertRaises(media_encoding.InvalidMedia):
                    media_encoding.mute_segments(Path("in.mp4"), target, bad, 20_000)

    def test_human_removal_and_restoration_record_rights_status(self):
        video = Video.objects.create(creator_id=uuid4(), title="Clip", state="published", visibility="public",
                                     provider_asset_id="playback/x.mp4", moderation_approved_at=timezone.now())
        self.assertEqual(_apply(video.id, uuid4(), "remove", 0).status_code, 200)
        video.refresh_from_db()
        self.assertEqual((video.state, video.rights_status), ("removed", "removed"))
        self.assertEqual(_apply(video.id, uuid4(), "restore", 1).status_code, 200)
        video.refresh_from_db()
        self.assertEqual((video.state, video.rights_status), ("published", "restored"))

    def test_blocklist_command_blocks_every_print_of_a_takedown(self):
        video = Video.objects.create(creator_id=uuid4(), title="Clip")
        Fingerprint.objects.create(video=video, kind="sha256", value="a")
        Fingerprint.objects.create(video=video, kind="pdq", value="b")
        call_command("block_video_fingerprints", str(video.id), stdout=StringIO())
        self.assertEqual(Fingerprint.objects.filter(blocked=True).count(), 2)
        self.assertTrue(ScreeningRecord.objects.filter(video=video, action="block").exists())
