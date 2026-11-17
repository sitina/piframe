"""Private, bounded, atomic photo checkpoints. Never deserialize executable data."""
import hashlib
import io
import json
import math
import os
from pathlib import Path
import stat
import struct
import tempfile
import threading
import time

from .image_processor import ImageProcessor

MAGIC = b'PIFRAME1\n'


class LastPhotoStore:
    def __init__(self, config):
        if not isinstance(config.last_photo_enabled, bool):
            raise ValueError("last_photo_enabled must be a boolean")
        self.config = config
        self.path = Path(config.last_photo_file)
        self.processor = ImageProcessor(config)
        self._lock = threading.RLock()
        self._last_attempt = None
        for value in (config.last_photo_max_age, config.last_photo_write_interval):
            if (isinstance(value, bool) or not isinstance(value, (int, float)) or
                    not math.isfinite(value) or value <= 0):
                raise ValueError('Photo checkpoint ages must be finite and positive')

    def _private_parent(self, create=False):
        if create:
            self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.path.parent.is_symlink():
            raise ValueError('Photo checkpoint directory must not be a symlink')
        if os.name == 'posix' and stat.S_IMODE(self.path.parent.stat().st_mode) & 0o077:
            raise ValueError('Photo checkpoint directory must be private')

    def save(self, prepared, metadata_factory=None):
        if not self.config.last_photo_enabled:
            return False
        with self._lock:
            now = time.monotonic()
            if (self._last_attempt is not None and
                    now - self._last_attempt < self.config.last_photo_write_interval):
                return False
            # Failed attempts back off too, before metadata parsing or decoding.
            self._last_attempt = now
            self._private_parent(create=True)
            temporary = None
            try:
                # Fail early for read-only/full storage, before expensive image work.
                descriptor, temporary = tempfile.mkstemp(dir=self.path.parent, prefix='.photo-')
                with os.fdopen(descriptor, 'wb') as stream:
                    data = prepared.image_data.getvalue()
                    image_format, _ = self.processor.verify_decodable(io.BytesIO(data))
                    name = ''.join(c for c in str(prepared.image_info.get('name', 'photo'))
                                   if ord(c) >= 32 and ord(c) != 127)[:256]
                    info = {'id': str(prepared.image_info['id'])[:1024], 'name': name or 'photo',
                            'type': {'JPEG': 'image/jpeg', 'PNG': 'image/png', 'GIF': 'image/gif',
                                     'BMP': 'image/bmp', 'WEBP': 'image/webp'}[image_format]}
                    metadata = prepared.metadata_info
                    if metadata is None and metadata_factory is not None:
                        metadata = metadata_factory()
                    header = json.dumps({'schema': 1, 'album_id': self.config.album_id,
                                         'saved_at': time.time(), 'info': info,
                                         'metadata': metadata or {},
                                         'sha256': hashlib.sha256(data).hexdigest()}, allow_nan=False).encode()
                    if len(header) > self.config.max_metadata_bytes:
                        raise ValueError('Photo checkpoint metadata exceeds budget')
                    stream.write(MAGIC)
                    stream.write(struct.pack('!I', len(header)))
                    stream.write(header)
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, self.path)
                temporary = None
                if os.name == 'posix':
                    directory = os.open(self.path.parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
                    try:
                        os.fsync(directory)
                    finally:
                        os.close(directory)
                return True
            finally:
                if temporary is not None:
                    Path(temporary).unlink(missing_ok=True)

    def load(self):
        if not self.config.last_photo_enabled or not self.path.exists():
            return None
        with self._lock:
            self._private_parent()
            descriptor = os.open(self.path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
            with os.fdopen(descriptor, 'rb') as stream:
                status = os.fstat(stream.fileno())
                limit = len(MAGIC) + 4 + self.config.max_metadata_bytes + self.config.max_download_bytes
                if (not stat.S_ISREG(status.st_mode) or status.st_size > limit or
                        (os.name == 'posix' and stat.S_IMODE(status.st_mode) & 0o077)):
                    raise ValueError('Invalid or non-private photo checkpoint')
                if stream.read(len(MAGIC)) != MAGIC:
                    raise ValueError('Invalid photo checkpoint format')
                raw_length = stream.read(4)
                if len(raw_length) != 4:
                    raise ValueError('Truncated photo checkpoint')
                length = struct.unpack('!I', raw_length)[0]
                if length > self.config.max_metadata_bytes:
                    raise ValueError('Photo checkpoint metadata exceeds budget')
                header = json.loads(stream.read(length))
                data = stream.read(self.config.max_download_bytes + 1)
            if not isinstance(header, dict) or header.get('schema') != 1:
                raise ValueError('Unsupported photo checkpoint schema')
            if header.get('album_id') != self.config.album_id:
                return None
            saved_at = header.get('saved_at')
            if isinstance(saved_at, bool) or not isinstance(saved_at, (int, float)) or not math.isfinite(saved_at):
                raise ValueError('Invalid photo checkpoint timestamp')
            age = time.time() - saved_at
            if age < 0 or age >= self.config.last_photo_max_age:
                return None
            if hashlib.sha256(data).hexdigest() != header.get('sha256'):
                raise ValueError('Photo checkpoint digest mismatch')
            info, metadata = header.get('info'), header.get('metadata')
            if (not isinstance(info, dict) or any(not isinstance(info.get(k), str) for k in ('id', 'name', 'type')) or
                    not isinstance(metadata, dict)):
                raise ValueError('Invalid photo checkpoint metadata')
            image_format, _ = self.processor.verify_decodable(io.BytesIO(data))
            expected_mime = {'JPEG': 'image/jpeg', 'PNG': 'image/png', 'GIF': 'image/gif',
                             'BMP': 'image/bmp', 'WEBP': 'image/webp'}[image_format]
            if (info['type'] != expected_mime or len(info['id']) > 1024 or len(info['name']) > 256 or
                    any(ord(c) < 32 or ord(c) == 127 for c in info['name']) or
                    not isinstance(metadata.get('display_info', {}), dict)):
                raise ValueError('Invalid photo checkpoint fields')
            return info, data, metadata
