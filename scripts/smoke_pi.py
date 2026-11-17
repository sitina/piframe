#!/usr/bin/env python3
"""Exercise native image/chart libraries; optionally require a live Drive photo."""
import hashlib
import io
import json
import re
import sys
from urllib.request import urlopen

from PIL import Image


def check_live_photo(base, opener=urlopen):
    with opener(base + '/random-picture/metadata', timeout=30) as response:
        metadata = json.load(response)
    path = metadata.get('picture_url', '')
    if metadata.get('image_source') != 'live':
        raise RuntimeError('Live Drive photo required; offline checkpoint cannot validate activation')
    if not metadata.get('image_id') or not re.fullmatch(r'/random-picture/snapshots/[a-f0-9]{32}', path):
        raise RuntimeError('No live photo snapshot available')
    with opener(base + path, timeout=30) as response:
        payload = response.read(16 * 1024 * 1024 + 1)
        source = response.headers.get('X-Photo-Source')
        image_hash = response.headers.get('X-Image-Hash')
    if len(payload) > 16 * 1024 * 1024:
        raise RuntimeError('Photo exceeds smoke-test budget')
    digest = hashlib.sha256(payload).hexdigest()[:16]
    if source != 'live' or digest != metadata.get('image_hash') or digest != image_hash:
        raise RuntimeError('Photo provenance or hash mismatch')
    Image.open(io.BytesIO(payload)).verify()


def main():
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib.figure import Figure
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
        check_live_photo(sys.argv[1])
    print('Image, chart and native-library smoke checks passed')


if __name__ == '__main__':
    main()
