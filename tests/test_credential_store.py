import os
import pickle
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from google.oauth2.credentials import Credentials
from piframe.services.credential_store import CredentialStore, CredentialStoreError, LegacyTokenError


class TestCredentialStore(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.store = CredentialStore(self.root / 'credentials' / 'token.json')
        self.creds = Credentials('fixture-token', refresh_token='fixture-refresh',
                                 client_id='fixture-client', client_secret='fixture-secret',
                                 token_uri='https://oauth2.googleapis.com/token')

    def test_json_round_trip_and_permissions(self):
        self.store.save(self.creds)
        self.assertEqual(self.store.load().refresh_token, 'fixture-refresh')
        if os.name == 'posix':
            self.assertEqual(self.store.path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(self.store.path.parent.stat().st_mode & 0o777, 0o700)

    def test_failed_replace_preserves_previous_token_and_cleans_temporary(self):
        self.store.save(self.creds)
        original = self.store.path.read_bytes()
        with patch('os.replace', side_effect=OSError('interrupted')):
            with self.assertRaises(CredentialStoreError):
                self.store.save(self.creds)
        self.assertEqual(self.store.path.read_bytes(), original)
        self.assertEqual(list(self.store.path.parent.iterdir()), [self.store.path])

    def test_malformed_json_is_not_deleted(self):
        self.store.save(self.creds)
        for content in ['{', '[]', '{}']:
            self.store.path.write_text(content)
            with self.assertRaises(CredentialStoreError):
                self.store.load()
            self.assertEqual(self.store.path.read_text(), content)

    def test_legacy_pickle_is_never_executed_by_runtime(self):
        legacy = self.root / 'token.pickle'
        legacy.write_bytes(pickle.dumps(self.creds))
        with patch('pickle.load', side_effect=AssertionError('unsafe unpickle')):
            with self.assertRaises(LegacyTokenError):
                CredentialStore(legacy).load()
        self.assertTrue(legacy.exists())

    def test_missing_token_is_distinct_from_corruption(self):
        self.assertIsNone(self.store.load())

    def test_explicit_migration_preserves_source_and_refuses_overwrite(self):
        source = self.root / 'legacy.pickle'
        source.write_bytes(pickle.dumps(self.creds))
        command = [sys.executable, 'scripts/migrate_token.py', '--source', str(source),
                   '--destination', str(self.store.path)]
        denied = subprocess.run(command, capture_output=True)
        self.assertNotEqual(denied.returncode, 0)
        self.assertFalse(self.store.path.exists())
        migrated = subprocess.run(command + ['--trust-local-pickle'], capture_output=True)
        self.assertEqual(migrated.returncode, 0, migrated.stderr)
        original = source.read_bytes()
        repeated = subprocess.run(command + ['--trust-local-pickle'], capture_output=True)
        self.assertNotEqual(repeated.returncode, 0)
        self.assertEqual(source.read_bytes(), original)
        self.assertEqual(self.store.load().refresh_token, 'fixture-refresh')
