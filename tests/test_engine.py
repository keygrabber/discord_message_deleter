"""Offline tests for the engine and services (no network, no GUI). Run: python -m unittest"""

import threading
import unittest
from datetime import datetime, timezone

from freeredact_app.core import ApiError, Filters, HttpClient, Item, Runner, Service
from freeredact_app.services.discord import DiscordService
from freeredact_app.services.reddit import RedditService


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

    def test_delete_skips_filtered_and_survives_failures(self):
        svc = FakeService([Item("1", "m", "keep"), Item("2", "m", "drop"), Item("3", "m", "drop")],
                          fail_ids=["2"])
        logs = self.run_runner(svc, dry_run=False, filters=Filters(keyword="drop"))
        self.assertEqual(svc.deleted, ["3"])
        self.assertTrue(any("Failed" in line for line in logs))


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


class RedditTest(unittest.TestCase):
    def test_scan_and_vote_reset(self):
        svc = RedditService({"client_id": "a", "client_secret": "b", "username": "u",
                             "password": "p"}, threading.Event(), lambda _m: None)
        calls = []

        def fake(method, path, **kwargs):
            calls.append((method, path, kwargs.get("data")))
            if method == "GET":
                return FakeResponse(200, {"data": {"after": None, "children": [
                    {"data": {"name": "t1_abc", "body": "hello", "created_utc": 1700000000}}]}})
            return FakeResponse(200, {})

        svc.http.request = fake
        items = list(svc.scan({"what": ["comments"]}, []))
        self.assertEqual((items[0].id, items[0].kind, items[0].text), ("t1_abc", "comment", "hello"))
        svc.delete(Item("t3_x", "upvote"))
        svc.delete(items[0])
        self.assertEqual(calls[-2], ("POST", "/api/vote", {"id": "t3_x", "dir": 0}))
        self.assertEqual(calls[-1], ("POST", "/api/del", {"id": "t1_abc"}))


if __name__ == "__main__":
    unittest.main()
