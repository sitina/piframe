"""Bounded immutable photo snapshots shared safely by concurrent viewers."""
from collections import OrderedDict
from dataclasses import dataclass
import hashlib
import json
import math
import secrets
import threading
import time


@dataclass(frozen=True)
class ImageSnapshot:
    token: str
    data: bytes
    info_json: str
    metadata_json: str
    timestamp: float
    created_monotonic: float

    @property
    def info(self):
        return json.loads(self.info_json)

    @property
    def metadata(self):
        return json.loads(self.metadata_json)

    @property
    def image_id(self):
        return self.info['id']

    @property
    def image_hash(self):
        return hashlib.sha256(self.data).hexdigest()[:16]

    @property
    def snapshot_id(self):
        return self.token

    @property
    def age(self):
        return time.monotonic() - self.created_monotonic

    @property
    def size(self):
        return len(self.data) + len(self.info_json.encode()) + len(self.metadata_json.encode())


class SnapshotStore:
    def __init__(self, config):
        self.max_bytes = config.snapshot_cache_max_bytes
        self.max_count = config.snapshot_cache_size
        self.ttl = config.snapshot_cache_ttl
        for value in (self.max_bytes, self.max_count):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError('Snapshot size budgets must be positive integers')
        if (isinstance(self.ttl, bool) or not isinstance(self.ttl, (int, float)) or
                not math.isfinite(self.ttl) or self.ttl <= 0):
            raise ValueError('Snapshot lifetime must be finite and positive')
        self._entries = OrderedDict()
        self._lock = threading.RLock()

    def publish(self, prepared):
        snapshot = ImageSnapshot(
            secrets.token_hex(16), prepared.image_data.getvalue(),
            json.dumps(prepared.image_info), json.dumps(prepared.metadata_info or {}),
            time.time(), time.monotonic())
        if snapshot.size > self.max_bytes:
            raise ValueError('Snapshot exceeds retained byte budget')
        with self._lock:
            self._cleanup()
            self._entries[snapshot.token] = snapshot
            while (len(self._entries) > self.max_count or
                   sum(entry.size for entry in self._entries.values()) > self.max_bytes):
                self._entries.popitem(last=False)
        return snapshot

    def _cleanup(self):
        for token in list(self._entries):
            if self._entries[token].age >= self.ttl:
                del self._entries[token]

    def get(self, token):
        # Tokens are opaque capabilities, never Google Drive IDs or filesystem paths.
        if not isinstance(token, str) or len(token) != 32 or any(c not in '0123456789abcdef' for c in token):
            return None
        with self._lock:
            self._cleanup()
            return self._entries.get(token)

    def latest(self):
        with self._lock:
            self._cleanup()
            return next(reversed(self._entries.values()), None)

    def clear(self):
        with self._lock:
            self._entries.clear()
