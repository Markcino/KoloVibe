"""Phase 11, test group 3: engagement and points over real HTTP, a real TLS RabbitMQ and the production Points worker.

Needs the full stack (broker and worker): run through runner.py WITHOUT --attach.
"""

import json
import secrets
import subprocess
import time
import unittest
import uuid

import lib
from lib import eventually
from psycopg import sql


def S():
    return lib.CURRENT


class Engagement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.creator, tokens = S().signed_in()
        me = S().get("/me", token=tokens["access_token"])[1]
        cls.creator_account = me["id"]
        S().arm_fixture_videos(cls.creator_account)
        cls.creator_token = S().login(cls.creator)["access_token"]
        cls.videos = [v["id"] for v in S().get("/videos")[1]["items"]]

    # ---- helpers ------------------------------------------------------------------------------------------
    def viewer(self):
        return S().signed_in()[1]["access_token"]

    def start(self, token, video=None):
        status, body = S().call("POST", f"/videos/{video or self.videos[0]}/watch-sessions", None, token=token)
        self.assertEqual(status, 200, body)
        return body["session_id"]

    def progress(self, token, session, position=2600, video=None):
        return S().post("/engagement/watch-events", {"video_id": video or self.videos[0], "session_id": session, "position_ms": position}, token=token)

    def watch_fully(self, token, video=None):
        session = self.start(token, video)
        time.sleep(3.3)
        for _ in range(2):
            status, body = self.progress(token, session, video=video)
            self.assertEqual(status, 200, body)
        return session

    def points(self):
        return S().get("/creators/me/points", token=self.creator_token)[1]

    def ledger(self):
        with S().db("points") as c:
            return c.execute("select count(*), coalesce(sum(delta),0) from points.points_entries where creator_user_id=%s",
                             (self.creator_account,)).fetchone()

    def award_arrives(self, before, expected=1, seconds=40):
        eventually(lambda: self.ledger()[0] >= before + expected, seconds, "the award never reached the ledger")
        time.sleep(1.0)
        self.assertEqual(self.ledger()[0], before + expected, "exactly the expected number of ledger entries")

    # ---- likes and follows ------------------------------------------------------------------------------------
    def test_T3_01_like_is_idempotent_and_reversible_and_private_to_the_account(self):
        a, b = self.viewer(), self.viewer()
        video = self.videos[1]
        self.assertIn(S().call("PUT", f"/videos/{video}/like", None, token=a)[0], (200, 204))
        self.assertIn(S().call("PUT", f"/videos/{video}/like", None, token=a)[0], (200, 204), "liking twice must not fail or double count")
        status, mine = S().get(f"/videos/{video}/like", token=a)
        self.assertEqual(status, 200)
        self.assertTrue(mine.get("liked") is True, mine)
        self.assertFalse(S().get(f"/videos/{video}/like", token=b)[1].get("liked"), "another account must not inherit the like")
        self.assertIn(S().call("DELETE", f"/videos/{video}/like", None, token=a)[0], (200, 204))
        self.assertFalse(S().get(f"/videos/{video}/like", token=a)[1].get("liked"))

    def test_T3_02_like_requires_authentication_and_a_real_video(self):
        self.assertEqual(S().call("PUT", f"/videos/{self.videos[1]}/like", None)[0], 401)
        self.assertEqual(S().call("PUT", f"/videos/{uuid.uuid4()}/like", None, token=self.viewer())[0], 404)
        self.assertEqual(S().call("PUT", "/videos/not-a-uuid/like", None, token=self.viewer())[0], 404)

    def test_T3_03_follow_is_idempotent_and_a_creator_cannot_follow_themselves(self):
        a = self.viewer()
        creator_profile = S().creator_id
        self.assertIn(S().call("PUT", f"/creators/{creator_profile}/follow", None, token=a)[0], (200, 204))
        self.assertIn(S().call("PUT", f"/creators/{creator_profile}/follow", None, token=a)[0], (200, 204))
        self.assertEqual(S().get(f"/creators/{creator_profile}/follow", token=a)[1].get("following"), True)
        self.assertIn(S().call("DELETE", f"/creators/{creator_profile}/follow", None, token=a)[0], (200, 204))
        status, _ = S().call("PUT", f"/creators/{creator_profile}/follow", None, token=self.creator_token)
        self.assertIn(status, (400, 403, 409), "a creator following themselves should be refused")

    # ---- watch integrity ----------------------------------------------------------------------------------------
    def test_T3_10_a_self_view_does_not_qualify(self):
        status, body = S().call("POST", f"/videos/{self.videos[0]}/watch-sessions", None, token=self.creator_token)
        self.assertEqual(status, 403, body)

    def test_T3_11_progress_that_is_faster_than_real_time_does_not_qualify(self):
        token = self.viewer()
        session = self.start(token)
        status, body = self.progress(token, session, 2600)  # no real time has passed
        self.assertNotEqual((status, body), (200, {"qualified": True}), "a claim of 2.6 s watched after 0 s elapsed must not qualify")
        self.assertIn(status, (200, 409), (status, body))

    def test_T3_12_backwards_oversized_and_malformed_progress_is_refused(self):
        token = self.viewer()
        session = self.start(token)
        for position in (-1, 300_001, 10**12, "2600", None, 2600.5, True):
            self.assertEqual(self.progress(token, session, position)[0], 400, position)
        self.assertEqual(S().post("/engagement/watch-events", {"video_id": self.videos[0], "session_id": session}, token=token)[0], 400)
        self.assertEqual(S().post("/engagement/watch-events", {"video_id": self.videos[0], "session_id": session, "position_ms": 1, "extra": 1}, token=token)[0], 400)

    def test_T3_13_a_session_cannot_be_used_by_another_account_or_for_another_video(self):
        a, b = self.viewer(), self.viewer()
        session = self.start(a)
        time.sleep(3.3)
        status, body = self.progress(b, session)
        self.assertIn(status, (400, 403, 404, 409), (status, body))
        self.assertNotEqual(body, {"qualified": True}, "another account must not be able to qualify a view for someone else's session")
        status, body = self.progress(a, session, video=self.videos[2])
        self.assertNotEqual((status, body), (200, {"qualified": True}), "a session is bound to its video")

    def test_T3_14_an_unauthenticated_or_unknown_session_is_refused(self):
        self.assertEqual(S().post("/engagement/watch-events", {"video_id": self.videos[0], "session_id": str(uuid.uuid4()), "position_ms": 100})[0], 401)
        status, _ = self.progress(self.viewer(), str(uuid.uuid4()))
        self.assertIn(status, (400, 404, 409))

    # ---- qualified views, duplicates, points --------------------------------------------------------------------
    def test_T3_20_a_qualified_view_becomes_exactly_one_ledger_entry_through_the_real_broker(self):
        before = self.ledger()[0]
        self.watch_fully(self.viewer(), self.videos[3])
        code, output = S().dispatch()
        self.assertEqual(code, 0, output)
        self.award_arrives(before, 1)
        body = self.points()
        self.assertGreaterEqual(body["confirmed"], 1)
        entries = S().get("/creators/me/points/entries", token=self.creator_token)[1]
        self.assertTrue(entries["items"], entries)

    def test_T3_21_repeated_progress_and_a_second_session_in_the_dedupe_window_give_one_award(self):
        token, before = self.viewer(), self.ledger()[0]
        first = self.watch_fully(token, self.videos[4])
        for _ in range(3):  # replayed progress of the same session
            self.assertEqual(self.progress(token, first, video=self.videos[4])[0], 200)
        self.watch_fully(token, self.videos[4])  # the same viewer, same video, a new session within 24 hours
        S().dispatch()
        self.award_arrives(before, 1)

    def test_T3_22_the_same_outbox_event_published_twice_is_applied_once(self):
        token, before = self.viewer(), self.ledger()[0]
        self.watch_fully(token, self.videos[5])
        S().dispatch()
        self.award_arrives(before, 1)
        with S().db("engagement") as c:
            c.execute("update engagement.event_outbox set published_at = null")  # redelivery of every event, including old ones
        S().dispatch()
        time.sleep(4)
        self.assertEqual(self.ledger()[0], before + 1, "a redelivered event must not create a second entry")

    def test_T3_23_points_data_is_private_to_the_creator_and_entries_are_object_scoped(self):
        entries = S().get("/creators/me/points/entries", token=self.creator_token)[1]["items"]
        if not entries:
            self.skipTest("no entries yet")
        entry = entries[0]["id"]
        other_creator, tokens = S().signed_in()
        self.assertIn(S().get("/creators/me/points", token=tokens["access_token"])[0], (403, 404), "a viewer has no points ledger")
        self.assertIn(S().get(f"/creators/me/points/entries/{entry}", token=tokens["access_token"])[0], (403, 404))
        # a second creator account must get 404 for the first creator's entry
        me2 = S().get("/me", token=tokens["access_token"])[1]
        with S().db("identity") as c:
            c.execute("UPDATE identity.service_account SET role='creator' WHERE id=%s", (me2["id"],))
        t2 = S().login(other_creator)["access_token"]
        self.assertIn(S().get(f"/creators/me/points/entries/{entry}", token=t2)[0], (403, 404))

    def test_T3_24_the_ledger_is_append_only_for_the_service_role_and_every_entry_is_attributable(self):
        with S().db("points") as c:
            row = c.execute("select entry_id, rule_version, reason_code, source_decision_id from points.points_entries limit 1").fetchone()
            self.assertIsNotNone(row, "no ledger rows to inspect")
            self.assertEqual(row[1], "DEC-003-v1")
            self.assertTrue(row[2] and row[3])
            for statement in ("update points.points_entries set delta=99 where entry_id=%s", "delete from points.points_entries where entry_id=%s"):
                with self.assertRaises(Exception, msg=statement):
                    c.execute(statement, (row[0],))

    def test_T3_90_the_daily_cap_withholds_further_awards_and_records_them(self):
        base = self.ledger()[0]
        with S().db("points") as c:
            table = c.execute("select table_name from information_schema.tables where table_schema='points' and table_name like '%dailyaward%'").fetchone()[0]
            today = c.execute(sql.SQL("select coalesce(sum(awards),0) from points.{} where creator_user_id=%s and day=(now() at time zone 'utc')::date").format(sql.Identifier(table)), (self.creator_account,)).fetchone()[0]
        needed = 100 - today + 3
        tokens = [self.viewer() for _ in range(needed)]
        # The 15-second sample-gap rule (an anti-fraud control) rejects stale sessions, so work in small timed batches.
        for offset in range(0, needed, 8):
            batch = list(enumerate(tokens))[offset:offset + 8]
            sessions = [(i, t, self.start(t, self.videos[6 + (i % 10)])) for i, t in batch]
            time.sleep(3.4)
            for i, t, s in sessions:
                for _ in range(2):
                    self.progress(t, s, video=self.videos[6 + (i % 10)])
        S().dispatch()

        def settled():
            with S().db("points") as c:
                tables = [r[0] for r in c.execute("select table_name from information_schema.tables where table_schema='points'").fetchall()]
                receipts = next(x for x in tables if "receipt" in x)
                counts = dict(c.execute(sql.SQL("select status, count(*) from points.{} where creator_user_id=%s group by status").format(sql.Identifier(receipts)), (self.creator_account,)).fetchall())
            return counts if counts.get("pending", 0) == 0 and counts.get("withheld", 0) >= 1 else None

        try:
            counts = eventually(settled, 150, "receipts never settled")
        except AssertionError:
            with S().db("points") as c:
                tables = [r[0] for r in c.execute("select table_name from information_schema.tables where table_schema='points'").fetchall()]
                receipts = next(x for x in tables if "receipt" in x)
                counts = dict(c.execute(sql.SQL("select status, count(*) from points.{} where creator_user_id=%s group by status").format(sql.Identifier(receipts)), (self.creator_account,)).fetchall())
            self.fail(f"cap test did not settle: receipts {counts}; needed {needed}; ledger {self.ledger()}; points {self.points()}")
        self.assertGreaterEqual(counts.get("withheld", 0), 1, f"nothing was withheld at the cap: {counts}")
        with S().db("points") as c:
            awards = c.execute(sql.SQL("select awards from points.{} where creator_user_id=%s and day=(now() at time zone 'utc')::date").format(sql.Identifier(table)), (self.creator_account,)).fetchone()[0]
        self.assertLessEqual(awards, 100, "the daily cap of 100 must never be exceeded")

    # ---- broker behaviour ---------------------------------------------------------------------------------------
    def test_T3_30_a_broker_outage_keeps_the_event_and_one_award_follows_recovery(self):
        before = self.ledger()[0]
        self.watch_fully(self.viewer(), self.videos[16])
        S().broker.ctl("stop_app")
        try:
            code, output = S().dispatch()
            self.assertNotEqual(code, 0, "dispatch must fail loudly while the broker is down: " + output)
            with S().db("engagement") as c:
                self.assertGreaterEqual(c.execute("select count(*) from engagement.event_outbox where published_at is null").fetchone()[0], 1)
        finally:
            S().broker.ctl("start_app", timeout=120)
        eventually(lambda: S().broker.consumers("kolovibe.points") >= 1, 60, "the worker did not reconnect")
        self.assertEqual(S().dispatch()[0], 0)
        self.award_arrives(before, 1)

    def test_T3_31_a_killed_consumer_loses_nothing_and_a_restarted_one_processes_once(self):
        before = self.ledger()[0]
        S().stop_worker(kill=True)
        eventually(lambda: S().broker.consumers("kolovibe.points") == 0, 30, "worker still registered")
        self.watch_fully(self.viewer(), self.videos[17])
        self.assertEqual(S().dispatch()[0], 0)
        eventually(lambda: S().broker.queue_state("kolovibe.points")[0] >= 1, 20, "the message was not held in the durable queue")
        self.assertEqual(self.ledger()[0], before, "nothing may be applied without a consumer")
        S().start_worker()
        eventually(lambda: S().broker.consumers("kolovibe.points") >= 1, 60, "worker did not start")
        self.award_arrives(before, 1)

    def test_T3_32_queued_messages_survive_a_broker_restart(self):
        before = self.ledger()[0]
        S().stop_worker(kill=True)
        eventually(lambda: S().broker.consumers("kolovibe.points") == 0, 30, "worker still registered")
        self.watch_fully(self.viewer(), self.videos[18])
        self.assertEqual(S().dispatch()[0], 0)
        eventually(lambda: S().broker.queue_state("kolovibe.points")[0] >= 1, 20, "message not queued")
        S().broker.ctl("stop_app")
        S().broker.ctl("start_app", timeout=120)
        eventually(lambda: S().broker.queue_state("kolovibe.points")[0] >= 1, 30, "the persistent message did not survive a broker restart")
        S().start_worker()
        eventually(lambda: S().broker.consumers("kolovibe.points") >= 1, 60, "worker did not start")
        self.award_arrives(before, 1)

    def _publish_raw(self, payload, headers):
        from kombu import Exchange

        with S().broker.connection("points") as connection:
            connection.Producer().publish(payload, exchange=Exchange("kolovibe.points", no_declare=True), routing_key="kolovibe.points",
                                          declare=[], retry=False, headers=headers)

    def _alive(self):
        return S().worker is not None and S().worker.poll() is None

    def test_T3_33_garbage_that_is_not_a_task_is_discarded_without_harming_the_worker(self):
        before = self.ledger()[0]
        for payload in ({"id": "x"}, [1, 2, 3], "garbage"):
            self._publish_raw(payload, {})
        eventually(lambda: S().broker.queue_state("kolovibe.points") == (0, 0), 30, "garbage messages are stuck or looping in the queue")
        self.assertTrue(self._alive(), "the worker must survive messages that are not tasks")
        self.watch_fully(self.viewer(), self.videos[19])
        S().dispatch()
        self.award_arrives(before, 1)

    def test_T3_35_a_malformed_task_envelope_must_not_kill_the_consumer_or_poison_the_queue(self):
        """Only an account with WRITE on the Points exchange can send this, but a poison pill must not become an outage.

        Reproduction found in Phase 11: a message with a `task` header and a JSON list or dict body (for example [1, 2, 3])
        raises KeyError('id') in Celery's on_task_received, which is unrecoverable for the worker; the message is
        redelivered after each restart, so the consumer never recovers until the queue is purged by hand.
        """
        self.assertTrue(self._alive())
        self._publish_raw([1, 2, 3], {"task": "kolovibe.points.event"})
        time.sleep(6)
        survived = self._alive()
        recovered = None
        if not survived:
            S().start_worker()
            time.sleep(10)
            recovered = self._alive() and S().broker.queue_state("kolovibe.points") == (0, 0)
        try:
            self.assertTrue(survived, "the Points worker died on a malformed envelope"
                            + ("" if recovered is None else (" and a restarted worker recovered" if recovered else " and a restarted worker died again on the redelivered message (crash loop)")))
        finally:
            S().stop_worker(kill=True)
            S().broker.ctl("purge_queue", "-p", lib.VHOST, "kolovibe.points", check=False)
            S().start_worker()
            eventually(lambda: S().broker.consumers("kolovibe.points") >= 1, 60, "worker did not restart")

    def test_T3_34_a_forged_qualified_view_event_cannot_be_injected_by_engagement_or_a_client(self):
        """A client cannot reach the queue at all; the engagement account cannot consume or declare (see Phase 10); here, over HTTP."""
        before = self.ledger()[0]
        self.assertEqual(S().post("/engagement/watch-events", {"video_id": self.videos[0], "session_id": str(uuid.uuid4()), "position_ms": 100}, token=self.viewer())[0] in (400, 404, 409), True)
        for path in ("/internal/engagement/watch/start", "/internal/likes"):
            for port in ("gateway",):
                status = S().call("POST", path, {}, port=port, api=False)[0]
                self.assertIn(status, (401, 403, 404), f"{path} must not be reachable through the public gateway")
        time.sleep(1)
        self.assertEqual(self.ledger()[0], before)
