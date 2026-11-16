"""Regression coverage for logging from a fresh checkout."""

import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from piframe.utils.logging import setup_logging


class TestLoggingSetup(unittest.TestCase):
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
