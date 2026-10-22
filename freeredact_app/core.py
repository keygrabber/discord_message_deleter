"""Service-independent engine: items, filters, HTTP client and the scan/delete runner.

Nothing in this module imports a GUI toolkit, so it can be tested headless.
"""

import json
import random
import threading
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, FrozenSet, Iterator, List, Optional, Sequence, Tuple

import requests


class Stopped(Exception):
    """Raised inside the worker when the user pressed Stop."""


class ApiError(Exception):
    """A request failed permanently (after retries) or returned an unexpected status."""


@dataclass
class Item:
    """One deletable thing (message, reaction, comment, vote...)."""

    id: str
    kind: str
    text: str = ""
    created: Optional[datetime] = None
    data: Dict[str, str] = field(default_factory=dict)
    tags: FrozenSet[str] = frozenset()  # content traits, e.g. {"attachment", "link"}


@dataclass
class Filters:
    """Optional filters; an item must satisfy all that are set.

    `content_types` keeps only items having at least one of the given tags; it
    applies to messages only (reactions have no content to inspect).
    """

    keyword: str = ""
    after: Optional[datetime] = None
    before: Optional[datetime] = None
    content_types: FrozenSet[str] = frozenset()

    def matches(self, item: Item) -> bool:
        """Return True if `item` passes keyword/date/content filters (dates are UTC)."""
        if self.keyword and self.keyword.lower() not in (item.text or "").lower():
            return False
        if self.content_types and item.kind == "message" and not (item.tags & self.content_types):
            return False
        if item.created is not None:
            created = item.created
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if self.after and created < self.after:
                return False
            if self.before and created > self.before:
                return False
        elif self.after or self.before:
            return False
        return True


@dataclass
class Field:
    """A credential input shown in the GUI."""

    key: str
    label: str
    secret: bool = False


@dataclass
class Choice:
    """A group of options. `multi` groups are checkboxes, others radio buttons.

    `options` is a sequence of (value, label) pairs.
    """

    key: str
    label: str
    options: Sequence[Tuple[str, str]]
    multi: bool = False
    default: Optional[Tuple[str, ...]] = None  # None = first option; () = nothing preselected
    required: bool = True  # multi groups: at least one option must be ticked


class HttpClient:
    """Thin `requests.Session` wrapper: timeouts, bounded retries, stop-aware waits.

    Retries on network errors, HTTP 5xx and HTTP 429 (honouring `retry_after` /
    `Retry-After`). Any other status is returned to the caller untouched.
    """

    def __init__(self, base_url: str, stop: threading.Event,
                 log: Callable[[str], None], headers: Optional[Dict[str, str]] = None,
                 timeout: float = 20, max_retries: int = 5):
        self.base_url = base_url.rstrip("/")
        self.stop = stop
        self.log = log
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        if headers:
            self.session.headers.update(headers)

    def sleep(self, seconds: float) -> None:
        """Wait `seconds`, waking immediately (and raising Stopped) if Stop is pressed."""
        if self.stop.wait(max(0.0, seconds)):
            raise Stopped()

    def request(self, method: str, path: str, **kwargs) -> requests.Response:
        """Send a request; `path` may be relative to `base_url` or an absolute URL."""
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        kwargs.setdefault("timeout", self.timeout)
        last_error = "unknown error"
        for attempt in range(self.max_retries + 1):
            if self.stop.is_set():
                raise Stopped()
            try:
                resp = self.session.request(method, url, **kwargs)
            except requests.RequestException as exc:
                last_error = type(exc).__name__
                self.log(f"  Network error ({last_error}), retrying...")
                self.sleep(min(2 ** attempt, 30))
                continue

            if resp.status_code == 429:
                wait = self._retry_after(resp)
                self.log(f"  Rate limited, waiting {wait:.1f}s...")
                self.sleep(wait + 1)
                last_error = "rate limited"
                continue
            if resp.status_code >= 500:
                last_error = f"HTTP {resp.status_code}"
                self.sleep(min(2 ** attempt, 30))
                continue
            return resp
        raise ApiError(f"{method} {url}: giving up ({last_error})")

    @staticmethod
    def _retry_after(resp: requests.Response) -> float:
        """Read the wait time from the JSON body or the Retry-After header."""
        try:
            return float(resp.json().get("retry_after"))
        except (ValueError, TypeError, AttributeError):
            pass
        try:
            return float(resp.headers.get("Retry-After"))
        except (ValueError, TypeError):
            return 5.0


class Service:
    """Base class for a platform (Discord, Reddit, ...)."""

    name = ""
    credentials: List[Field] = []
    choices: List[Choice] = []
    ids_label = ""  # when set, the GUI shows an ID box for `needs_ids` selections

    def __init__(self, creds: Dict[str, str], stop: threading.Event,
                 log: Callable[[str], None]):
        self.creds = creds
        self.stop = stop
        self.log = log

    @classmethod
    def needs_ids(cls, selection: Dict[str, object]) -> bool:
        """Whether the current selection requires the user to paste IDs."""
        return False

    def login(self) -> str:
        """Authenticate; return a display name. Raise ApiError on failure."""
        raise NotImplementedError

    def scan(self, selection: Dict[str, object], ids: List[str]) -> Iterator[Item]:
        """Yield every candidate item. Must not delete anything."""
        raise NotImplementedError

    def scan_batches(self, selection: Dict[str, object],
                     ids: List[str]) -> Iterator[List[Item]]:
        """Yield candidates in batches (e.g. one per channel) so deleting can start early.

        The default puts everything into a single batch.
        """
        yield list(self.scan(selection, ids))

    def delete(self, item: Item) -> None:
        """Delete/undo one item. Raise ApiError if it failed."""
        raise NotImplementedError


class Archive:
    """Append-only JSON Lines file with one record per removed (or previewed) item.

    Lets you keep a private local copy of what was deleted. The file is flushed
    after every record so a crash or Stop never loses entries.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "a", encoding="utf-8")

    def write(self, item: Item, action: str) -> None:
        """Append one record describing `item` and what happened to it."""
        record = {
            "action": action,
            "kind": item.kind,
            "id": item.id,
            "created": item.created.isoformat() if item.created else None,
            "text": item.text,
            "tags": sorted(item.tags),
            "data": item.data,
        }
        self._fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._fh.flush()

    def close(self) -> None:
        """Close the file (safe to call twice)."""
        if not self._fh.closed:
            self._fh.close()


class Runner:
    """Walks the service batch by batch; unless `dry_run`, deletes each matching item.

    Processing batch by batch (one Discord channel at a time) means deletions start
    right away and pressing Stop keeps everything already done.
    """

    def __init__(self, service: Service, selection: Dict[str, object], ids: List[str],
                 filters: Filters, dry_run: bool, delay: Tuple[float, float],
                 stop: threading.Event, log: Callable[[str], None],
                 progress: Callable[[int, int], None] = lambda done, total: None,
                 on_done: Callable[[], None] = lambda: None,
                 archive: Optional["Archive"] = None):
        self.service = service
        self.selection = selection
        self.ids = ids
        self.filters = filters
        self.dry_run = dry_run
        self.delay = delay
        self.stop = stop
        self.log = log
        self.progress = progress
        self.on_done = on_done
        self.archive = archive

    def run(self) -> None:
        """Entry point for the worker thread; never raises."""
        try:
            self._run()
        except Stopped:
            self.log(">>> Stopped.")
        except Exception as exc:  # worker must not die silently
            self.log(f"!!! Error: {exc}")
        finally:
            if self.archive:
                self.archive.close()
            self.on_done()

    def _archive(self, item: Item, action: str) -> None:
        """Record `item` in the archive, if one is attached."""
        if self.archive:
            self.archive.write(item, action)

    def _run(self) -> None:
        name = self.service.login()
        self.log(f"Logged in as {name}.")

        found = handled = deleted = failed = 0
        paused = False  # becomes True after the first deletion; pause before the next one
        for batch in self.service.scan_batches(self.selection, self.ids):
            matching = [item for item in batch if self.filters.matches(item)]
            found += len(matching)
            for item in matching:
                if self.stop.is_set():
                    raise Stopped()
                if self.dry_run:
                    self.log(f"  [PREVIEW] {item.kind} {item.id}: {_short(item.text)}")
                    self._archive(item, "preview")
                else:
                    if paused and self.stop.wait(random.uniform(*self.delay)):
                        raise Stopped()
                    try:
                        self.service.delete(item)
                        deleted += 1
                        self.log(f"  Deleted {item.kind} {item.id}")
                        self._archive(item, "deleted")
                    except ApiError as exc:
                        failed += 1
                        self.log(f"  Failed {item.kind} {item.id}: {exc}")
                    paused = True
                handled += 1
                self.progress(handled, found)
            self.progress(handled, found)

        if self.dry_run:
            self.log(f"Preview done. Nothing was deleted ({found} would be).")
        else:
            self.log(f"Done. Deleted {deleted}, failed {failed}.")


def _short(text: str, limit: int = 60) -> str:
    """One-line, truncated version of `text` for log output."""
    text = " ".join((text or "[no text]").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"
