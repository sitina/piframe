import io
import unittest
from unittest.mock import Mock, patch

from scripts import authenticate
from piframe.config import Config


class TestAuthenticateCommand(unittest.TestCase):
    def test_explicit_command_binds_loopback_and_limits_wait(self):
        flow = Mock()
        flow.run_local_server.return_value = Mock(valid=True, refresh_token='fixture-refresh')
        with patch('sys.argv', ['authenticate.py', '--no-browser']), \
             patch.object(authenticate.Config, 'load', return_value=Config()), \
             patch.object(authenticate.InstalledAppFlow, 'from_client_secrets_file', return_value=flow), \
             patch.object(authenticate, 'CredentialStore') as store:
            self.assertEqual(authenticate.main(), 0)
            flow.run_local_server.assert_called_once_with(
                host='localhost', bind_addr='127.0.0.1', port=8085,
                open_browser=False, timeout_seconds=180,
                access_type='offline', prompt='consent')
            store.return_value.save.assert_called_once_with(flow.run_local_server.return_value)

    def test_auth_failure_does_not_save_or_print_secret_exception(self):
        flow = Mock()
        flow.run_local_server.side_effect = TimeoutError('FAKE_SECRET')
        with patch('sys.argv', ['authenticate.py']), \
             patch.object(authenticate.Config, 'load', return_value=Config()), \
             patch.object(authenticate.InstalledAppFlow, 'from_client_secrets_file', return_value=flow), \
             patch.object(authenticate, 'CredentialStore') as store, \
             patch('sys.stderr', new_callable=io.StringIO) as output:
            self.assertEqual(authenticate.main(), 1)
            store.assert_not_called()
            self.assertNotIn('FAKE_SECRET', output.getvalue())

    def test_access_token_only_result_cannot_replace_refreshable_credentials(self):
        flow = Mock()
        flow.run_local_server.return_value = Mock(valid=True, refresh_token=None)
        with patch('sys.argv', ['authenticate.py']), \
             patch.object(authenticate.Config, 'load', return_value=Config()), \
             patch.object(authenticate.InstalledAppFlow, 'from_client_secrets_file', return_value=flow), \
             patch.object(authenticate, 'CredentialStore') as store, \
             patch('sys.stdout', new_callable=io.StringIO) as output:
            self.assertEqual(authenticate.main(), 1)
            store.assert_not_called()
            self.assertNotIn('Credentials saved', output.getvalue())
