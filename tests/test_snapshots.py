import hashlib
import io
import unittest
from unittest.mock import Mock, patch
from flask import Flask, jsonify
from PIL import Image
from piframe.config import Config
from piframe.models.cache import CacheManager
from piframe.services.image_service import ImageService


class TestSnapshots(unittest.TestCase):
    def setUp(self):
        self.config = Config(snapshot_cache_size=2)
        self.drive = Mock()
        self.service = ImageService(self.config, self.drive, CacheManager(self.config))
        self.addCleanup(self.service.close)
        self.app = Flask(__name__)
        self.app.add_url_rule('/metadata', view_func=lambda: jsonify(self.service.get_random_image_metadata()))
        self.app.add_url_rule('/random-picture/snapshots/<token>', view_func=self.service.serve_snapshot)
        self.photos = []
        for color in ('red', 'blue', 'green'):
            data = io.BytesIO()
            Image.new('RGB', (10, 20), color).save(data, 'JPEG')
            self.photos.append(data.getvalue())
        self.drive.get_random_image.return_value = {
            'id': 'same-mutable-drive-id', 'name': 'photo.jpg', 'type': 'image/jpeg'}
        self.drive.download_file.side_effect = [io.BytesIO(photo) for photo in self.photos]

    def test_two_clients_keep_exact_bytes_and_metadata_after_another_selection(self):
        a, b = self.app.test_client(), self.app.test_client()
        metadata_a = a.get('/metadata').json
        metadata_b = b.get('/metadata').json
        self.assertNotEqual(metadata_a['picture_url'], metadata_b['picture_url'])
        for client, metadata, expected in ((a, metadata_a, self.photos[0]), (b, metadata_b, self.photos[1])):
            response = client.get(metadata['picture_url'])
            self.assertEqual(response.data, expected)
            self.assertEqual(response.headers['X-Image-Hash'], metadata['image_hash'])
            self.assertEqual(metadata['image_hash'], hashlib.sha256(expected).hexdigest()[:16])
        self.assertEqual(self.drive.download_file.call_count, 2)
        self.assertEqual(self.service.cache_manager.get_cache('metadata').stats()['entry_count'], 2)

    def test_exif_newlines_and_unicode_stay_in_json_not_http_headers(self):
        data = io.BytesIO()
        exif = Image.Exif()
        exif[271] = 'Camera\nMake'
        Image.new('RGB', (10, 20)).save(data, 'JPEG', exif=exif)
        self.drive.download_file.side_effect = None
        self.drive.download_file.return_value = data
        client = self.app.test_client()
        metadata = client.get('/metadata').json
        response = client.get(metadata['picture_url'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, data.getvalue())
        self.assertNotIn('X-Camera-Info', response.headers)

    def test_evicted_or_invalid_token_never_selects_another_photo(self):
        client = self.app.test_client()
        old = client.get('/metadata').json
        client.get('/metadata')
        client.get('/metadata')
        self.assertEqual(client.get(old['picture_url']).status_code, 404)
        self.assertEqual(client.get('/random-picture/snapshots/drive-file-id').status_code, 404)
        self.assertEqual(self.drive.download_file.call_count, 3)

    def test_expired_snapshot_is_not_served_or_redownloaded(self):
        client = self.app.test_client()
        metadata = client.get('/metadata').json
        snapshot = self.service.snapshots.latest()
        with patch('piframe.services.snapshots.time.monotonic', return_value=snapshot.created_monotonic + 301):
            self.assertEqual(client.get(metadata['picture_url']).status_code, 404)
        self.assertEqual(self.drive.download_file.call_count, 1)
