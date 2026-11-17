"""Resource limits for untrusted album images and metadata parsing."""

import io
from PIL import Image


class ImageRejected(ValueError):
    pass


class BoundedImageBuffer(io.BytesIO):
    def __init__(self, limit):
        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise ValueError("Download budget must be a positive integer")
        super().__init__()
        self.limit = limit

    def write(self, data):
        if self.tell() + len(data) > self.limit:
            raise ImageRejected('Image exceeds download byte budget')
        return super().write(data)


class ImageProcessor:
    FORMATS = ('JPEG', 'PNG', 'GIF', 'BMP', 'WEBP')

    def __init__(self, config):
        for name in ("max_download_bytes", "max_image_pixels", "max_metadata_bytes"):
            value = getattr(config, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        self.config = config

    def inspect(self, data):
        if data.getbuffer().nbytes > self.config.max_download_bytes:
            raise ImageRejected('Image exceeds byte budget')
        # Private bounded stream: closing Pillow must not close the response data.
        stream = io.BytesIO(data.getvalue())
        image = None
        try:
            image = Image.open(stream, formats=self.FORMATS)
            if image.width * image.height > self.config.max_image_pixels:
                raise ImageRejected('Image exceeds pixel budget')
            return image.format, image.size
        except (OSError, SyntaxError, Image.DecompressionBombError) as error:
            raise ImageRejected('Unsupported or malformed image') from error
        finally:
            if image is not None:
                image.close()
            stream.close()

    def verify_decodable(self, data):
        """Decode one bounded frame before trusting an offline checkpoint."""
        result = self.inspect(data)
        try:
            with Image.open(io.BytesIO(data.getvalue()), formats=self.FORMATS) as image:
                image.load()
        except (OSError, SyntaxError, Image.DecompressionBombError) as error:
            raise ImageRejected('Image frame cannot be decoded') from error
        return result
