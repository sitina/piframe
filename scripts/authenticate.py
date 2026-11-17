#!/usr/bin/env python3
"""Explicit, bounded OAuth setup for an operator, separate from the server."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from google_auth_oauthlib.flow import InstalledAppFlow
from piframe.config import Config
from piframe.services.credential_store import CredentialStore, CredentialStoreError
from piframe.services.drive_service import DriveService


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='config/config.json')
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--port', type=int, default=8085)
    args = parser.parse_args()
    try:
        config = Config.load(args.config)
        flow = InstalledAppFlow.from_client_secrets_file(
            config.drive_credentials_file, DriveService.SCOPES)
        credentials = flow.run_local_server(
            host='localhost', bind_addr='127.0.0.1', port=args.port,
            open_browser=not args.no_browser, timeout_seconds=180,
            access_type='offline', prompt='consent')
        if not credentials.valid or not isinstance(credentials.refresh_token, str) or not credentials.refresh_token.strip():
            raise ValueError('Unattended operation requires valid refreshable credentials')
    except Exception as error:
        print(f'Authentication failed ({type(error).__name__}); inspect setup and retry.', file=sys.stderr)
        return 1
    try:
        CredentialStore(config.drive_token_file).save(credentials)
    except CredentialStoreError as error:
        print(f'Credentials obtained but could not be saved: {error}', file=sys.stderr)
        return 1
    except Exception as error:
        print(f'Credentials obtained but could not be saved ({type(error).__name__}); check destination storage.', file=sys.stderr)
        return 1
    print('Credentials saved. The frame can now start unattended.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
