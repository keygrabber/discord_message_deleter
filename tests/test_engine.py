"""Offline tests for the engine and services (no network, no GUI). Run: python -m unittest"""

import json
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path

from freeredact_app.core import ApiError, Archive, Filters, HttpClient, Item, Runner, Service
from freeredact_app.services.discord import DiscordService


def utc(y, m, d):
    """UTC datetime helper."""
    return datetime(y, m, d, tzinfo=timezone.utc)


class FakeResponse:
    """Minimal stand-in for requests.Response."""

    def __init__(self, status=200, body=None, headers=None):
        self.status_code = status
        self._body = body
        self.headers = headers or {"content-type": "application/json"}

    def json(self):
        return self._body


class FiltersTest(unittest.TestCase):
    def test_keyword_is_case_insensitive(self):
        self.assertTrue(Filters(keyword="HeLLo").matches(Item("1", "m", "say hello there")))
        self.assertFalse(Filters(keyword="bye").matches(Item("1", "m", "say hello")))

    def test_date_range(self):
        f = Filters(after=utc(2024, 1, 1), before=utc(2024, 12, 31))
        self.assertTrue(f.matches(Item("1", "m", "", utc(2024, 6, 1))))
        self.assertFalse(f.matches(Item("2", "m", "", utc(2023, 6, 1))))
        self.assertFalse(f.matches(Item("3", "m", "", utc(2025, 6, 1))))

    def test_undated_item_fails_date_filter_only(self):
        self.assertTrue(Filters().matches(Item("1", "m", "x")))
        self.assertFalse(Filters(after=utc(2024, 1, 1)).matches(Item("1", "m", "x")))

    def test_content_types_apply_to_messages_only(self):
        f = Filters(content_types=frozenset({"attachment"}))
        self.assertTrue(f.matches(Item("1", "message", "", tags=frozenset({"attachment", "link"}))))
        self.assertFalse(f.matches(Item("2", "message", "plain text")))
        self.assertTrue(f.matches(Item("3", "reaction", "party on 1")))


class HttpClientTest(unittest.TestCase):
    def make(self, responses):
        client = HttpClient("https://example.test", threading.Event(), lambda _m: None)
        client.sleep = lambda _s: None
        queue = list(responses)
        client.session.request = lambda *a, **k: queue.pop(0)
        return client

    def test_retries_rate_limit_then_succeeds(self):
        client = self.make([FakeResponse(429, {"retry_after": 0.1}), FakeResponse(200, {})])
        self.assertEqual(client.request("GET", "/x").status_code, 200)

    def test_gives_up_after_max_retries(self):
        client = self.make([FakeResponse(500)] * 6)
        with self.assertRaises(ApiError):
            client.request("GET", "/x")


class FakeService(Service):
    name = "Fake"

    def __init__(self, items, fail_ids=()):
        super().__init__({}, threading.Event(), lambda _m: None)
        self.items, self.fail_ids, self.deleted = items, set(fail_ids), []

    def login(self):
        return "tester"

    def scan(self, selection, ids):
        yield from self.items

    def delete(self, item):
        if item.id in self.fail_ids:
            raise ApiError("boom")
        self.deleted.append(item.id)


class RunnerTest(unittest.TestCase):
    def run_runner(self, service, dry_run, filters=None):
        logs, done = [], []
        Runner(service, {}, [], filters or Filters(), dry_run, (0, 0), service.stop,
               logs.append, on_done=lambda: done.append(True)).run()
        self.assertEqual(done, [True])
        return logs

    def test_preview_deletes_nothing(self):
        svc = FakeService([Item("1", "message", "a"), Item("2", "message", "b")])
        self.run_runner(svc, dry_run=True)
        self.assertEqual(svc.deleted, [])

    def test_stats_report_found_deleted_failed(self):
        svc = FakeService([Item("1", "m", "a"), Item("2", "m", "b")], fail_ids=["2"])
        seen = []
        Runner(svc, {}, [], Filters(), False, (0, 0), svc.stop, lambda _m: None,
               stats=lambda f, d, x: seen.append((f, d, x))).run()
        self.assertEqual(seen[-1], (2, 1, 1))

    def test_delete_skips_filtered_and_survives_failures(self):
        svc = FakeService([Item("1", "m", "keep"), Item("2", "m", "drop"), Item("3", "m", "drop")],
                          fail_ids=["2"])
        logs = self.run_runner(svc, dry_run=False, filters=Filters(keyword="drop"))
        self.assertEqual(svc.deleted, ["3"])
        self.assertTrue(any("Failed" in line for line in logs))

    def test_archive_records_only_successful_deletions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.jsonl"
            svc = FakeService([Item("1", "m", "héllo"), Item("2", "m", "bad")], fail_ids=["2"])
            Runner(svc, {}, [], Filters(), False, (0, 0), svc.stop, lambda _m: None,
                   archive=Archive(path)).run()
            records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([(r["id"], r["action"], r["text"]) for r in records],
                         [("1", "deleted", "héllo")])


class BatchTest(unittest.TestCase):
    def test_deletes_batch_before_scanning_next(self):
        order = []

        class Batched(FakeService):
            def scan_batches(self, selection, ids):
                for n in (1, 2):
                    order.append(f"scan{n}")
                    yield [Item(str(n), "m", "x")]

            def delete(self, item):
                order.append(f"del{item.id}")

        svc = Batched([])
        Runner(svc, {}, [], Filters(), False, (0, 0), svc.stop, lambda _m: None).run()
        self.assertEqual(order, ["scan1", "del1", "scan2", "del2"])

    def test_stop_before_first_item_deletes_nothing(self):
        svc = FakeService([Item("1", "m", "x")])
        svc.stop.set()
        Runner(svc, {}, [], Filters(), False, (0, 0), svc.stop, lambda _m: None).run()
        self.assertEqual(svc.deleted, [])


class DiscordTest(unittest.TestCase):
    def make(self, pages):
        svc = DiscordService({"token": "x"}, threading.Event(), lambda _m: None)
        svc.me = "me"
        calls = []

        def fake(method, path, **kwargs):
            calls.append((method, path))
            if method == "GET" and path.endswith("/messages"):
                return FakeResponse(200, pages.pop(0) if pages else [])
            return FakeResponse(204, None)

        svc.http.request = fake
        return svc, calls

    def test_scan_messages_and_reactions(self):
        mine = {"id": "10", "author": {"id": "me"}, "content": "hi", "type": 0,
                "timestamp": "2024-05-01T10:00:00.000000+00:00",
                "reactions": [{"me": True, "emoji": {"id": "77", "name": "party"}},
                              {"me": False, "emoji": {"id": None, "name": "x"}}]}
        theirs = {"id": "9", "author": {"id": "other"}, "content": "yo", "type": 0,
                  "timestamp": "2024-05-01T09:00:00.000000+00:00"}
        system = {"id": "8", "author": {"id": "me"}, "content": "", "type": 7,
                  "timestamp": "2024-05-01T08:00:00.000000+00:00"}
        svc, _ = self.make([[mine, theirs, system]])
        items = list(svc.scan({"what": ["messages", "reactions"], "scope": "selected"}, ["123"]))
        self.assertEqual([(i.kind, i.id) for i in items],
                         [("message", "10"), ("reaction", "10/party:77")])
        self.assertEqual(items[0].created, datetime(2024, 5, 1, 10, tzinfo=timezone.utc))

    def test_picked_scope_only_scans_chosen_servers(self):
        svc, _ = self.make([])
        guilds = [{"id": "g1", "name": "Zeta"}, {"id": "g2", "name": "alpha"}]
        routes = {"/users/@me/guilds": guilds,
                  "/guilds/g1/channels": [{"id": "c1", "type": 0}],
                  "/guilds/g2/channels": [{"id": "c2", "type": 0}]}
        svc.http.request = lambda method, path, **kw: FakeResponse(200, routes[path])
        self.assertEqual(svc._channel_ids("picked", ["g2"]), ["c2"])
        self.assertEqual(svc.list_choices(), [("g2", "alpha"), ("g1", "Zeta")])

    def test_server_scope_adds_threads_only_when_requested(self):
        svc, _ = self.make([])
        archived = {"threads": [{"id": "t2", "thread_metadata": {
            "archive_timestamp": "2024-01-01T00:00:00+00:00"}}], "has_more": False}
        routes = {
            "/users/@me/guilds": [{"id": "g", "name": "G"}],
            "/guilds/g/channels": [{"id": "c1", "type": 0}, {"id": "f1", "type": 15},
                                   {"id": "v", "type": 2}],
            "/guilds/g/threads/active": {"threads": [{"id": "t1"}]},
            "/channels/c1/threads/archived/public": archived,
            "/channels/f1/threads/archived/public": {"threads": [{"id": "t1"}], "has_more": False},
        }
        svc.http.request = lambda method, path, **kw: (
            FakeResponse(200, routes[path]) if path in routes else FakeResponse(404, {}))
        self.assertEqual(svc._channel_ids("servers", [], True), ["c1", "t1", "t2"])
        self.assertEqual(svc._channel_ids("servers", [], False), ["c1"])

    def test_delete_paths(self):
        svc, calls = self.make([])
        svc.delete(Item("10", "message", "", None, {"channel": "5"}))
        svc.delete(Item("10/😀", "reaction", "", None,
                        {"channel": "5", "message": "10", "emoji": "😀"}))
        self.assertEqual(calls[0], ("DELETE", "/channels/5/messages/10"))
        self.assertEqual(calls[1], ("DELETE", "/channels/5/messages/10/reactions/%F0%9F%98%80/@me"))

    def test_needs_ids_only_for_selected_scope(self):
        self.assertTrue(DiscordService.needs_ids({"scope": "selected"}))
        self.assertFalse(DiscordService.needs_ids({"scope": "dms"}))


if __name__ == "__main__":
    unittest.main()
