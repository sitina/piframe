import io
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch

from PIL import Image
from piframe.config import Config
from piframe.models.cache import CacheManager, TTLCache
from piframe.services.drive_service import DriveService
from piframe.services.image_processor import BoundedImageBuffer, ImageProcessor, ImageRejected
from piframe.utils.metadata import extract_image_metadata


class TestImageLimits(unittest.TestCase):
    def test_download_buffer_rejects_before_retaining_excess_bytes(self):
        buffer = BoundedImageBuffer(5)
        buffer.write(b'1234')
        with self.assertRaises(ImageRejected):
            buffer.write(b'56')
        self.assertEqual(buffer.getvalue(), b'1234')

    def test_payload_byte_budget_evicts_by_lru(self):
        cache = TTLCache(max_size=10, max_bytes=6)
        cache.set('a', b'1234')
        cache.set('b', b'5678')
        self.assertIsNone(cache.get('a'))
        self.assertEqual(cache.get('b'), b'5678')
        cache.set('oversize', b'1234567')
        self.assertEqual(cache.get('b'), b'5678')
        self.assertLessEqual(cache.stats()['retained_bytes'], 6)

    def test_image_pixel_format_and_metadata_budgets(self):
        image = io.BytesIO()
        Image.new('RGB', (100, 100)).save(image, 'JPEG')
        processor = ImageProcessor(Config(max_image_pixels=99))
        with self.assertRaises(ImageRejected):
            processor.inspect(image)
        with self.assertRaises(ImageRejected):
            ImageProcessor(Config()).inspect(io.BytesIO(b'<html>not an image</html>'))
        with patch('exifread.process_file', return_value={}) as parse:
            extract_image_metadata(image, max_metadata_bytes=30)
            self.assertEqual(len(parse.call_args.args[0].getvalue()), 30)

    def test_oversized_drive_file_is_rejected_before_media_request(self):
        config = Config(max_download_bytes=5)
        service = DriveService(config, CacheManager(config))
        service._service = Mock()
        service._service.files.return_value.get.return_value.execute.return_value = {'size': '6'}
        self.assertIsNone(service.download_file('big'))
        service._service.files.return_value.get_media.assert_not_called()

    def test_concurrent_cold_downloads_share_one_success(self):
        config = Config()
        service = DriveService(config, CacheManager(config))
        start = threading.Barrier(3)
        def fetch():
            start.wait(timeout=5)
            return service.download_file('same').getvalue()
        with patch.object(service, '_execute_download', return_value=io.BytesIO(b'fixture')) as execute:
            with ThreadPoolExecutor(max_workers=3) as pool:
                self.assertEqual(list(pool.map(lambda _: fetch(), range(3))), [b'fixture'] * 3)
        execute.assert_called_once()
