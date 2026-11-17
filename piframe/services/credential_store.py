"""Private, atomic persistence for Google credentials; no authentication I/O."""

import json
import os
import stat
import shlex
import tempfile
from pathlib import Path

from google.oauth2.credentials import Credentials


class CredentialStoreError(RuntimeError):
    pass


class CredentialPermissionError(CredentialStoreError):
    """Existing credential storage needs a permission or ownership repair."""


class LegacyTokenError(CredentialStoreError):
    pass


class CredentialStore:
    def __init__(self, token_file):
        configured = Path(token_file)
        if configured.suffix == '.pickle':
            self.legacy_path = configured
            self.path = configured.parent / 'credentials' / (configured.stem + '.json')
        else:
            self.path = configured
            self.legacy_path = (configured.parent.parent / 'token.pickle'
                                if configured.parent.name == 'credentials'
                                else configured.with_suffix('.pickle'))

    def _check_private_parent(self):
        if self.path.parent.is_symlink():
            raise CredentialStoreError('Credential directory must not be a symlink')
        if os.name == 'posix' and stat.S_IMODE(self.path.parent.stat().st_mode) & 0o077:
            raise CredentialPermissionError(
                f'Credential directory must be private; run chmod 700 {shlex.quote(str(self.path.parent))}')

    def load(self):
        if not self.path.exists():
            if self.legacy_path.exists():
                raise LegacyTokenError('Explicit trusted token migration required')
            return None
        try:
            self._check_private_parent()
            if self.path.is_symlink():
                raise CredentialStoreError('Credential file must not be a symlink')
            if os.name == 'posix' and stat.S_IMODE(self.path.stat().st_mode) & 0o077:
                raise CredentialPermissionError(
                    f'Credential file must be private; run chmod 600 {shlex.quote(str(self.path))}')
            data = json.loads(self.path.read_text())
            if not isinstance(data, dict):
                raise ValueError("Credential JSON must be an object")
            return Credentials.from_authorized_user_info(data)
        except PermissionError as error:
            raise CredentialPermissionError('Cannot read credentials; check file ownership and directory access') from error
        except (OSError, ValueError, TypeError, UnicodeError) as error:
            raise CredentialStoreError('Cannot read credential JSON; inspect the existing file and storage') from error

    def save(self, credentials):
        temporary = None
        try:
            self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            self._check_private_parent()
            descriptor, temporary = tempfile.mkstemp(dir=self.path.parent, prefix='.token-')
            with os.fdopen(descriptor, 'w') as stream:
                stream.write(credentials.to_json())
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            temporary = None
            if os.name == 'posix':
                directory = os.open(self.path.parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
        except PermissionError as error:
            raise CredentialPermissionError('Cannot save credentials; check directory ownership and write access') from error
        except (OSError, ValueError, TypeError) as error:
            raise CredentialStoreError('Cannot save credential JSON; check destination storage') from error
        finally:
            if temporary is not None:
                Path(temporary).unlink(missing_ok=True)
