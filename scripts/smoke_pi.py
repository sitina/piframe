#!/usr/bin/env python3
"""Exercise native image/chart libraries; optionally check a running frame."""
import io
import json
import sys
from urllib.request import urlopen

import matplotlib
matplotlib.use('Agg')
from matplotlib.figure import Figure
from PIL import Image
import numpy
import cryptography.hazmat.bindings._rust
import googleapiclient.discovery
import waitress

image = io.BytesIO()
Image.new('RGB', (16, 16), 'red').save(image, 'JPEG')
image.seek(0)
Image.open(image).verify()
chart = io.BytesIO()
figure = Figure()
figure.subplots().plot(numpy.arange(3), [1, 3, 2])
figure.savefig(chart, format='png')
Image.open(chart).verify()
if len(sys.argv) == 2:
    base = sys.argv[1]
    with urlopen(base + '/random-picture/metadata', timeout=30) as response:
        metadata = json.load(response)
    path = metadata.get('picture_url', '')
    if not metadata.get('image_id') or not path.startswith('/random-picture/'):
        raise RuntimeError('No authenticated photo available')
    with urlopen(base + path, timeout=30) as response:
        payload = response.read(16 * 1024 * 1024 + 1)
    if len(payload) > 16 * 1024 * 1024:
        raise RuntimeError('Photo exceeds smoke-test budget')
    Image.open(io.BytesIO(payload)).verify()
print('Image, chart and native-library smoke checks passed')
