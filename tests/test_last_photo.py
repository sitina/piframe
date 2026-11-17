import hashlib
import io
import os
from pathlib import Path
import tempfile
import threading
import requests
from werkzeug.serving import make_server
import unittest
from unittest.mock import Mock, patch
from flask import Flask, jsonify
from PIL import Image
from piframe.config import Config
from piframe.models.cache import CacheManager
from piframe.services.image_service import ImageService, PreparedImage
from piframe.services.last_photo_store import LastPhotoStore


class TestLastPhoto(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = Config(album_id='fixture', last_photo_file=str(Path(self.temp.name) / 'state/last-photo.bin'))
        self.store = LastPhotoStore(self.config)
        data = io.BytesIO()
        exif = Image.Exif()
        exif[271] = 'Camera\nMake'
        Image.new('RGB', (20, 10), 'red').save(data, 'JPEG', exif=exif)
        self.data = data.getvalue()
        self.prepared = PreparedImage({'id':'photo', 'name':'photo.jpg', 'type':'image/jpeg'},
                                      io.BytesIO(self.data), hashlib.sha256(self.data).hexdigest()[:16],
                                      {'display_info':{'creation_date':'fixture date','camera_info':'Camera\nMake'}})

    def test_atomic_failure_preserves_previous_photo_and_cleans_temporary(self):
        self.store.save(self.prepared)
        original = self.store.path.read_bytes()
        with patch.object(self.store, '_last_saved', None), patch('piframe.services.last_photo_store.os.replace', side_effect=OSError('fixture failure')):
            with self.assertRaises(OSError):
                self.store.save(self.prepared)
        self.assertEqual(self.store.path.read_bytes(), original)
        self.assertEqual(list(self.store.path.parent.glob('.photo-*')), [])
        if os.name == 'posix':
            self.assertEqual(self.store.path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(self.store.path.parent.stat().st_mode & 0o777, 0o700)

    def test_write_throttle_does_not_rewrite_or_extend_saved_age(self):
        with patch('piframe.services.last_photo_store.time.monotonic', return_value=100) as clock:
            self.assertTrue(self.store.save(self.prepared))
            original = self.store.path.read_bytes()
            clock.return_value = 120
            self.assertFalse(self.store.save(self.prepared))
            self.assertEqual(self.store.path.read_bytes(), original)
            clock.return_value = 401
            self.assertTrue(self.store.save(self.prepared))

    @patch('piframe.services.last_photo_store.time.time', return_value=1001)
    def test_corrupt_oversized_expired_future_or_wrong_album_is_not_reused(self, clock):
        with patch('piframe.services.last_photo_store.time.time', return_value=1000):
            self.store.save(self.prepared)
        original = self.store.path.read_bytes()
        with patch('piframe.services.last_photo_store.time.time', return_value=1000 + self.config.last_photo_max_age):
            self.assertIsNone(self.store.load())
        with patch('piframe.services.last_photo_store.time.time', return_value=999):
            self.assertIsNone(self.store.load())
        self.config.album_id = 'different-album'
        self.assertIsNone(self.store.load())
        self.config.album_id = 'fixture'
        self.store.path.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
        with self.assertRaises(ValueError):
            self.store.load()
        self.store.path.write_bytes(b'wrong format')
        with self.assertRaises(ValueError):
            self.store.load()
        self.store.path.write_bytes(original)
        self.config.max_download_bytes = 10
        with self.assertRaises(ValueError):
            self.store.load()

    def test_truncated_image_never_replaces_good_checkpoint(self):
        self.store.save(self.prepared)
        original = self.store.path.read_bytes()
        self.prepared.image_data = io.BytesIO(self.data[:-25])
        with patch.object(self.store, '_last_saved', None):
            with self.assertRaises(ValueError):
                self.store.save(self.prepared)
        self.assertEqual(self.store.path.read_bytes(), original)

    def test_symlinks_are_rejected_without_touching_target(self):
        self.store.save(self.prepared)
        target = self.store.path.with_name('original.bin')
        self.store.path.rename(target)
        self.store.path.symlink_to(target)
        before = target.read_bytes()
        with self.assertRaises(OSError):
            self.store.load()
        self.assertEqual(target.read_bytes(), before)

    def test_restart_offline_serves_checkpoint_and_metadata_without_renewal(self):
        drive = Mock()
        drive.get_random_image.return_value = self.prepared.image_info
        drive.download_file.return_value = io.BytesIO(self.data)
        live = ImageService(self.config, drive, CacheManager(self.config))
        app = Flask(__name__)
        with app.test_request_context():
            self.assertEqual(live.serve_random_image().status_code, 200)
        live.close()
        before = self.store.path.read_bytes()
        offline = Mock()
        offline.get_random_image.side_effect = RuntimeError('offline fixture')
        restarted = ImageService(self.config, offline, CacheManager(self.config))
        self.addCleanup(restarted.close)
        app.add_url_rule('/metadata', view_func=lambda: jsonify(restarted.get_random_image_metadata()))
        app.add_url_rule('/random-picture/snapshots/<token>', view_func=restarted.serve_snapshot)
        client = app.test_client()
        metadata = client.get('/metadata').json
        response = client.get(metadata['picture_url'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.data)
        self.assertEqual(response.headers['X-Image-Hash'], self.prepared.image_hash)
        self.assertEqual(self.store.path.read_bytes(), before)
        with app.test_request_context():
            self.assertEqual(restarted.serve_random_image().status_code, 200)

    def test_bootstrap_checkpoint_does_not_call_stalled_live_transport(self):
        self.store.save(self.prepared)
        stalled = Mock()
        stalled.get_random_image.side_effect = AssertionError('Live transport must not be contacted during bootstrap')
        service = ImageService(self.config, stalled, CacheManager(self.config))
        self.addCleanup(service.close)
        app = Flask(__name__)
        app.add_url_rule('/metadata', view_func=lambda: jsonify(service.get_random_image_metadata()))
        app.add_url_rule('/random-picture/snapshots/<token>', view_func=service.serve_snapshot)
        server = make_server('127.0.0.1', 0, app)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f'http://127.0.0.1:{server.server_port}'
            metadata = requests.get(base + '/metadata', timeout=5).json()
            response = requests.get(base + metadata['picture_url'], timeout=5)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content, self.data)
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
        stalled.get_random_image.assert_not_called()
        stalled.download_file.assert_not_called()

    def test_storage_failure_never_breaks_live_photo(self):
        drive = Mock()
        drive.get_random_image.return_value = self.prepared.image_info
        drive.download_file.return_value = io.BytesIO(self.data)
        service = ImageService(self.config, drive, CacheManager(self.config))
        self.addCleanup(service.close)
        with patch.object(service.last_photo, 'save', side_effect=OSError('read-only fixture')):
            with Flask(__name__).test_request_context():
                self.assertEqual(service.serve_random_image().status_code, 200)
