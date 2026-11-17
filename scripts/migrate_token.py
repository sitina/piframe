#!/usr/bin/env python3
"""One-time migration. Only use a pickle whose origin and integrity you trust."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from piframe.services.credential_store import CredentialStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default='config/token.pickle')
    parser.add_argument('--destination', default='config/credentials/token.json')
    parser.add_argument('--trust-local-pickle', action='store_true', required=True,
                        help='Acknowledge that unpickling this trusted file executes code')
    args = parser.parse_args()
    store = CredentialStore(args.destination)
    if store.path.exists():
        parser.error('Destination already exists; refusing to overwrite credentials')
    import pickle  # Never used by normal runtime credential loading.
    with open(args.source, 'rb') as source:
        credentials = pickle.load(source)
    store.save(credentials)
    print('Credential JSON saved; original token retained for rollback.')


if __name__ == '__main__':
    main()
