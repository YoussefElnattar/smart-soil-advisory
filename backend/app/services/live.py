"""Tiny in-process pub/sub used for Server-Sent Events (one-way live updates)."""

from __future__ import annotations

import asyncio
import json


class Broker:
    def __init__(self) -> None:
        self._subs: set[tuple[asyncio.Queue, int | None, asyncio.AbstractEventLoop]] = set()

    def subscribe(self, zone_id: int | None) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subs.add((q, zone_id, asyncio.get_running_loop()))
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subs = {s for s in self._subs if s[0] is not q}

    def publish(self, event: str, data: dict, zone_id: int | None = None) -> None:
        msg = f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        for q, zid, loop in list(self._subs):
            if zid is not None and zone_id is not None and zid != zone_id:
                continue
            try:
                loop.call_soon_threadsafe(q.put_nowait, msg)
            except (RuntimeError, asyncio.QueueFull):
                pass


broker = Broker()
