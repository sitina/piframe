"""Regression coverage for logging from a fresh checkout."""

import logging
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from piframe.utils.logging import setup_logging
from piframe.utils.logging import SecretSafeFormatter
from piframe.config import Config


class TestLoggingSetup(unittest.TestCase):
    def test_secrets_are_redacted_after_interpolation_and_in_tracebacks(self):
        output = io.StringIO()
        handler = logging.StreamHandler(output)
        handler.setFormatter(SecretSafeFormatter('%(message)s'))
        logger = logging.Logger('fixture')
        logger.addHandler(handler)
        logger.warning('Retrying %s', 'https://example.test/?appid=FAKE_QUERY&lat=50')
        try:
            raise RuntimeError('refresh_token="FAKE_REFRESH" Authorization: Bearer FAKE_BEARER')
        except RuntimeError:
            logger.exception('Request failed: %s', {'client_secret': 'FAKE_CLIENT'})
        text = output.getvalue()
        for secret in ['FAKE_QUERY', 'FAKE_REFRESH', 'FAKE_BEARER', 'FAKE_CLIENT']:
            self.assertNotIn(secret, text)
        self.assertIn('lat=50', text)
        self.assertIn('RuntimeError', text)

    def test_escaped_multiline_and_generic_tokens_are_fully_redacted(self):
        formatter = SecretSafeFormatter('%(message)s')
        payloads = [json.dumps({'refresh_token': 'prefix"LEAK_SENTINEL'}),
                    json.dumps({'token': 'LEAK_SENTINEL'}),
                    'password="prefix\nLEAK_SENTINEL"',
                    "client_secret='prefix\\'LEAK_SENTINEL'"]
        for payload in payloads:
            with self.subTest(payload=payload):
                record = logging.LogRecord('fixture', logging.ERROR, '', 0, '%s', (payload,), None)
                self.assertNotIn('LEAK_SENTINEL', formatter.format(record))
                try:
                    raise RuntimeError(payload)
                except RuntimeError:
                    import sys
                    record.exc_info = sys.exc_info()
                    self.assertNotIn('LEAK_SENTINEL', formatter.format(record))

    def test_config_representations_hide_all_secrets_but_persistence_keeps_them(self):
        config = Config(weather_api_key='FAKE_WEATHER', secret_key='FAKE_SECRET')
        for text in [str(config), repr(config)]:
            self.assertNotIn('FAKE_WEATHER', text)
            self.assertNotIn('FAKE_SECRET', text)
        self.assertEqual(config.to_dict()['secret_key'], 'FAKE_SECRET')

    def setUp(self):
        self.root = logging.getLogger()
        self.handlers = self.root.handlers[:]
        self.level = self.root.level
        self.addCleanup(self.restore_logging)

    def restore_logging(self):
        for handler in self.root.handlers:
            if handler not in self.handlers:
                handler.close()
        self.root.handlers = self.handlers
        self.root.setLevel(self.level)

    def test_creates_missing_log_directory_and_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            log_file = Path(directory) / 'nested' / 'logs' / 'piframe.log'
            try:
                setup_logging(str(log_file), enable_console=False)
                self.root.warning('fixture warning')
                self.assertIn('fixture warning', log_file.read_text())
            finally:
                # Release the file before removing the directory on Windows.
                self.restore_logging()

    def test_file_error_keeps_console_logging_available(self):
        with patch('piframe.utils.logging.Path.mkdir', side_effect=PermissionError), \
                patch('sys.stdout') as output:
            setup_logging('logs/piframe.log')
            self.root.warning('fixture warning')
            text = ''.join(str(call.args[0]) for call in output.write.call_args_list)
            self.assertIn('Could not set up file logging', text)
            self.assertIn('fixture warning', text)
