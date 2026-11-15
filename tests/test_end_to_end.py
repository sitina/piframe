"""Exercise real application services and libraries with fixture API transports.

Only external Google Drive and weather HTTP responses are substituted. Requests
to PiFrame use a live local HTTP server, including image parsing and chart output.
"""

import io
import json
import threading
import unittest
from urllib.parse import urlparse

import httplib2
import requests
from googleapiclient.discovery import build
from PIL import Image
from requests.adapters import BaseAdapter
from werkzeug.serving import make_server

from app import PiFrameApp
from piframe.config import Config
from piframe.models.cache import reset_cache_manager


class DriveFixtureTransport:
    """Supply Drive API wire responses without replacing the Drive service."""

    def __init__(self, photo):
        self.photo = photo
        self.calls = []

    def request(self, uri, method="GET", body=None, headers=None, **kwargs):
        self.calls.append(uri)
        if "/files?" in uri:
            data = json.dumps({"files": [{
                "id": "fixture-photo", "name": "fixture.jpg",
                "mimeType": "image/jpeg",
                "webViewLink": "fixture-view-link",
                "createdTime": "2026-11-01T12:34:56Z",
            }]}).encode()
            content_type = "application/json"
        elif "/files/fixture-photo?" in uri and "alt=media" in uri:
            data = self.photo
            content_type = "image/jpeg"
        else:
            raise AssertionError(f"Unexpected Drive request: {uri}")
        return httplib2.Response({
            "status": "200", "content-type": content_type,
            "content-length": str(len(data)),
        }), data

    def close(self):
        pass


class WeatherFixtureAdapter(BaseAdapter):
    """Return serialized weather responses through a real Requests session."""

    def __init__(self):
        self.paths = []

    def send(self, request, **kwargs):
        path = urlparse(request.url).path
        self.paths.append(path)
        weather = {
            "main": {"temp": 293.15, "feels_like": 292.15, "humidity": 60},
            "weather": [{"main": "Clear", "icon": "01d"}],
        }
        if path.endswith("/weather"):
            data = weather
        elif path.endswith("/forecast"):
            data = {"list": [dict(weather, dt_txt=f"2026-11-15 {hour:02}:00:00")
                             for hour in range(0, 24, 3)]}
        else:
            raise AssertionError(f"Unexpected weather request: {path}")
        response = requests.Response()
        response.status_code = 200
        response.url = request.url
        response.request = request
        response.headers["Content-Type"] = "application/json"
        response._content = json.dumps(data).encode()
        return response

    def close(self):
        pass


class TestEndToEnd(unittest.TestCase):
    def setUp(self):
        reset_cache_manager()
        self.frame = PiFrameApp(Config(
            album_id="fixture-album", weather_api_key="fixture-key",
            weather_location="Prague", secret_key="fixture-secret",
            weather_file_fallback="/nonexistent-piframe-fixture-forecast.json",
        ))
        self.addCleanup(self.frame.close)
        self.addCleanup(reset_cache_manager)

        photo = io.BytesIO()
        exif = Image.Exif()
        exif[306] = "2026:11:01 12:34:56"
        Image.new("RGB", (32, 24), "navy").save(photo, "JPEG", exif=exif)
        self.photo = photo.getvalue()
        self.drive_http = DriveFixtureTransport(self.photo)
        self.frame.drive_service._service = build(
            "drive", "v3", http=self.drive_http,
            cache_discovery=False, static_discovery=True,
        )
        self.weather_http = WeatherFixtureAdapter()
        self.frame.weather_service.session.mount(
            "https://api.openweathermap.org/", self.weather_http
        )

        self.server = make_server("127.0.0.1", 0, self.frame.app)
        self.addCleanup(self.server.server_close)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"
        self.client = requests.Session()
        self.client.trust_env = False
        self.addCleanup(self.client.close)

    def stop_server(self):
        self.server.shutdown()
        self.thread.join(timeout=5)

    def get(self, path):
        response = self.client.get(self.base_url + path, timeout=10)
        self.assertEqual(response.status_code, 200, response.text[:200])
        return response

    def test_photo_weather_metadata_and_chart(self):
        """Render pages, fetch a Drive photo, parse EXIF and generate a chart."""
        for path in ["/", "/fullscreen", "/picture", "/weather"]:
            self.assertIn("text/html", self.get(path).headers["Content-Type"])

        metadata = self.get("/random-picture/metadata").json()
        self.assertEqual(metadata["creation_date"], "1.11.2026")
        self.assertEqual(metadata["creation_time"], "12:34:56")
        self.assertEqual(metadata["dimensions"], "32 x 24")
        self.assertEqual(metadata["image_id"], "fixture-photo")

        for path in [metadata["picture_url"], "/random-picture", "/random-picture/new"]:
            response = self.get(path)
            self.assertEqual(response.headers["Content-Type"], "image/jpeg")
            self.assertEqual(response.content, self.photo)
            with Image.open(io.BytesIO(response.content)) as image:
                image.load()
                self.assertEqual(image.size, (32, 24))

        synchronized = self.get("/random-picture/synchronized-metadata").json()
        self.assertEqual(synchronized["image_hash"], metadata["image_hash"])
        chart = self.get("/weather/forecast.png")
        self.assertEqual(chart.headers["Content-Type"], "image/png")
        with Image.open(io.BytesIO(chart.content)) as image:
            image.load()
            self.assertEqual(image.format, "PNG")
            self.assertGreater(image.width, 100)

        self.assertEqual(self.get("/status").json()["photos"]["album_configured"], True)
        self.assertTrue(any("alt=media" in uri for uri in self.drive_http.calls))
        self.assertIn("/data/2.5/weather", self.weather_http.paths)
        self.assertIn("/data/2.5/forecast", self.weather_http.paths)


if __name__ == "__main__":
    unittest.main()
