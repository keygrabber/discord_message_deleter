"""Discord: delete your own messages and remove your own reactions.

Uses a user token (self-bot), which Discord's Terms of Service do not allow.
Use at your own risk and never share your token.
"""

from datetime import datetime
from typing import Dict, Iterator, List, Optional
from urllib.parse import quote

from ..core import ApiError, Choice, Field, HttpClient, Item, Service

API = "https://discord.com/api/v9"
TEXT_CHANNEL_TYPES = (0, 5)         # GUILD_TEXT, GUILD_ANNOUNCEMENT
DELETABLE_MESSAGE_TYPES = (0, 19, 20, 23)  # default, reply, slash command, context menu


class DiscordService(Service):
    """Messages and reactions in DMs, servers or specific channels."""

    name = "Discord"
    credentials = [Field("token", "Discord token", secret=True)]
    choices = [
        Choice("what", "What to remove", [
            ("messages", "My messages"),
            ("reactions", "My reactions"),
        ], multi=True),
        Choice("scope", "Where", [
            ("dms", "All DMs"),
            ("servers", "All servers"),
            ("selected", "Specific channel / DM IDs"),
        ]),
    ]
    ids_label = "Channel or DM IDs (comma separated)"

    def __init__(self, creds, stop, log):
        super().__init__(creds, stop, log)
        self.http = HttpClient(API, stop, log, headers={
            "Authorization": creds["token"].strip(),
            "Content-Type": "application/json",
        })
        self.me: Optional[str] = None

    @classmethod
    def needs_ids(cls, selection) -> bool:
        """IDs are only needed for the 'selected' scope."""
        return selection.get("scope") == "selected"

    def login(self) -> str:
        """Verify the token and remember our user ID."""
        r = self.http.request("GET", "/users/@me")
        if r.status_code != 200:
            raise ApiError(f"login failed ({r.status_code}) - check your token")
        user = r.json()
        self.me = user["id"]
        return user.get("username", self.me)

    def _channel_ids(self, scope: str, ids: List[str]) -> List[str]:
        """Resolve the list of channel IDs to scan for the chosen scope."""
        if scope == "selected":
            return ids
        if scope == "dms":
            r = self.http.request("GET", "/users/@me/channels")
            if r.status_code != 200:
                raise ApiError(f"cannot list DMs ({r.status_code})")
            channels = [c["id"] for c in r.json()]
            self.log(f"Found {len(channels)} private conversations.")
            return channels

        r = self.http.request("GET", "/users/@me/guilds")
        if r.status_code != 200:
            raise ApiError(f"cannot list servers ({r.status_code})")
        guilds = r.json()
        self.log(f"Found {len(guilds)} servers.")
        channels: List[str] = []
        for g in guilds:
            rc = self.http.request("GET", f"/guilds/{g['id']}/channels")
            if rc.status_code != 200:
                self.log(f"  Skipping '{g.get('name', g['id'])}': cannot list channels ({rc.status_code})")
                continue
            text = [c["id"] for c in rc.json() if c.get("type") in TEXT_CHANNEL_TYPES]
            self.log(f"  {g.get('name', g['id'])}: {len(text)} text channels")
            channels.extend(text)
        return channels

    def _history(self, channel_id: str) -> Iterator[dict]:
        """Yield every message of a channel, newest to oldest."""
        before = None
        while True:
            params = {"limit": 100}
            if before:
                params["before"] = before
            r = self.http.request("GET", f"/channels/{channel_id}/messages", params=params)
            if r.status_code != 200:
                self.log(f"  Cannot read channel {channel_id} ({r.status_code}), skipping.")
                return
            page = r.json()
            if not page:
                return
            yield from page
            before = page[-1]["id"]

    def _channel_items(self, cid: str, what: set) -> Iterator[Item]:
        """Yield own messages and/or own reactions found in one channel."""
        for msg in self._history(cid):
            created = _parse_time(msg.get("timestamp"))
            if ("messages" in what and msg["author"]["id"] == self.me
                    and msg.get("type", 0) in DELETABLE_MESSAGE_TYPES):
                yield Item(msg["id"], "message", msg.get("content") or "[media/embed]",
                           created, {"channel": cid})
            if "reactions" in what:
                for rx in msg.get("reactions") or []:
                    if not rx.get("me"):
                        continue
                    emoji = rx["emoji"]
                    ref = f"{emoji['name']}:{emoji['id']}" if emoji.get("id") else emoji["name"]
                    yield Item(f"{msg['id']}/{ref}", "reaction", f"{ref} on {msg['id']}",
                               created, {"channel": cid, "message": msg["id"], "emoji": ref})

    def scan_batches(self, selection: Dict[str, object],
                     ids: List[str]) -> Iterator[List[Item]]:
        """Yield one batch per channel so deleting starts after the first channel."""
        what = set(selection.get("what") or [])
        for cid in self._channel_ids(str(selection.get("scope")), ids):
            self.log(f"--- Channel {cid} ---")
            yield list(self._channel_items(cid, what))

    def scan(self, selection: Dict[str, object], ids: List[str]) -> Iterator[Item]:
        """Flat view of `scan_batches`."""
        for batch in self.scan_batches(selection, ids):
            yield from batch

    def delete(self, item: Item) -> None:
        """Delete a message or remove our reaction; an already-missing target counts as done."""
        if item.kind == "message":
            path = f"/channels/{item.data['channel']}/messages/{item.id}"
        else:
            path = (f"/channels/{item.data['channel']}/messages/{item.data['message']}"
                    f"/reactions/{quote(item.data['emoji'], safe='')}/@me")
        r = self.http.request("DELETE", path)
        if r.status_code not in (200, 204, 404):
            raise ApiError(f"HTTP {r.status_code}")


def _parse_time(value: Optional[str]) -> Optional[datetime]:
    """Parse Discord's ISO-8601 timestamp (tz-aware); None if missing/invalid."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
