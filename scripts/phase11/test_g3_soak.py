"""Phase 12, T3_92: sustained load with repeated failure injection on the real TLS broker and Points worker.

Many qualified views are produced over real HTTP, dispatched in several rounds while the Points worker is killed and the
broker application is stopped and started, then every outbox event is republished several more times. The secure outcome:
the queue drains, every distinct event produces exactly one receipt, the ledger never double counts, the daily cap holds,
and the worker is alive at the end.
"""

import os
import threading
import time
import unittest

import lib
from lib import eventually
from psycopg import sql

VIEWS = int(os.environ.get("SOAK_VIEWS", "240"))
REPUBLISH_ROUNDS = int(os.environ.get("SOAK_REPUBLISH", "4"))


def S():
    return lib.CURRENT


class Soak(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.creator, tokens = S().signed_in()
        cls.creator_account = S().get("/me", token=tokens["access_token"])[1]["id"]
        S().arm_fixture_videos(cls.creator_account)
        cls.videos = [v["id"] for v in S().get("/videos")[1]["items"]]

    def _tables(self):
        with S().db("points") as c:
            names = [r[0] for r in c.execute("select table_name from information_schema.tables where table_schema='points'").fetchall()]
        return next(x for x in names if "receipt" in x)

    def receipts(self):
        with S().db("points") as c:
            rows = c.execute(sql.SQL("select status, count(*) from points.{} where creator_user_id=%s group by status").format(
                sql.Identifier(self._tables())), (self.creator_account,)).fetchall()
        return dict(rows)

    def ledger(self):
        with S().db("points") as c:
            return c.execute("select count(*), coalesce(sum(delta),0) from points.points_entries where creator_user_id=%s",
                             (self.creator_account,)).fetchone()[0]

    def outbox(self):
        with S().db("engagement") as c:
            return c.execute("select count(*), count(*) filter (where published_at is null) from engagement.event_outbox").fetchone()

    def produce(self, count):
        tokens = [S().signed_in()[1]["access_token"] for _ in range(count)]
        for offset in range(0, count, 20):
            batch = list(enumerate(tokens))[offset:offset + 20]
            sessions = []
            for i, t in batch:
                video = self.videos[i % len(self.videos)]
                status, body = S().call("POST", f"/videos/{video}/watch-sessions", None, token=t)
                self.assertEqual(status, 200, body)
                sessions.append((t, video, body["session_id"]))
            time.sleep(3.4)
            for t, video, s in sessions:
                for _ in range(2):
                    S().post("/engagement/watch-events", {"video_id": video, "session_id": s, "position_ms": 2600}, token=t)

    def test_T3_92_sustained_load_with_worker_kills_and_a_broker_restart_applies_every_event_exactly_once(self):
        timings = {}
        t0 = time.monotonic()
        self.produce(VIEWS)
        timings["produce_s"] = round(time.monotonic() - t0, 1)
        events, _ = self.outbox()
        self.assertGreaterEqual(events, VIEWS * 0.9, f"too few qualified events were produced: {events}")

        stop = threading.Event()
        kills = []

        def chaos():  # kill the worker every 4 seconds while it consumes, then restart it
            while not stop.is_set():
                time.sleep(4)
                if stop.is_set():
                    break
                S().stop_worker(kill=True)
                kills.append(time.monotonic())
                time.sleep(1)
                S().start_worker()

        t1 = time.monotonic()
        chaos_thread = threading.Thread(target=chaos, daemon=True)
        chaos_thread.start()
        try:
            self.assertEqual(S().dispatch()[0], 0)
            time.sleep(6)
            S().broker.ctl("stop_app")
            time.sleep(3)
            S().broker.ctl("start_app", timeout=120)
            for _ in range(REPUBLISH_ROUNDS):  # every event again, including those already applied
                with S().db("engagement") as c:
                    c.execute("update engagement.event_outbox set published_at = null")
                code, output = S().dispatch()
                self.assertEqual(code, 0, output)
                time.sleep(3)
        finally:
            stop.set()
            chaos_thread.join(timeout=30)
        if S().worker is None or S().worker.poll() is not None:
            S().start_worker()
        eventually(lambda: S().broker.consumers("kolovibe.points") >= 1, 90, "worker did not reconnect")
        eventually(lambda: S().broker.queue_state("kolovibe.points") == (0, 0), 600, "the queue never drained")
        timings["drain_s"] = round(time.monotonic() - t1, 1)

        counts = self.receipts()
        total = sum(counts.values())
        ledger = self.ledger()
        print(f"SOAK events={events} messages_published~={events * (1 + REPUBLISH_ROUNDS)} worker_kills={len(kills)} "
              f"receipts={counts} ledger_entries={ledger} timings={timings}", flush=True)
        self.assertEqual(counts.get("pending", 0), 0, f"receipts left pending: {counts}")
        self.assertEqual(total, events, f"every distinct event must give exactly one receipt: {counts} vs {events} events")
        self.assertLessEqual(ledger, 100, "the daily cap of 100 must hold under load")
        self.assertEqual(ledger, counts.get("posted", 0), "ledger entries must match posted receipts")
        self.assertEqual(counts.get("legacy", 0), 0, f"no outcome may be unknown: {counts}")
        self.assertTrue(S().worker.poll() is None, "the worker must be alive at the end")
