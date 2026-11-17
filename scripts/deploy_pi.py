#!/usr/bin/env python3
"""Prepare, then explicitly activate a Bookworm or Trixie ARMv6 environment.

Never moves an existing venv. Keeps old environments for explicit rollback.
Requires the existing piframe.service to execute this checkout's scripts/start.sh.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import struct
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / 'requirements-pi-bookworm.txt'
CURRENT = ROOT / 'venv-current'


def check_target():
    error = ('Requires 32-bit ARMv6 Raspberry Pi OS: '
             'Bookworm/Python 3.11 or Trixie/Python 3.13')
    if platform.machine() != 'armv6l' or struct.calcsize('P') != 4:
        raise RuntimeError(error)
    try:
        release = platform.freedesktop_os_release()
    except OSError:
        raise RuntimeError(error) from None
    targets = {'12': ('bookworm', (3, 11)), '13': ('trixie', (3, 13))}
    target = targets.get(release.get('VERSION_ID'))
    if target is None or sys.version_info[:2] != target[1] or release.get('ID') != 'raspbian':
        raise RuntimeError(error)
    return target[0]


def run(*args):
    subprocess.run([str(arg) for arg in args], cwd=ROOT, check=True)


def lock_hash():
    return hashlib.sha256(LOCK.read_bytes()).hexdigest()


def smoke(candidate, live=False):
    args = [candidate / 'bin/python', ROOT / 'scripts/smoke_pi.py']
    if live:
        args.append('http://127.0.0.1:81')
    run(*args)


def switch(target):
    temporary = ROOT / ('.venv-switch-' + uuid.uuid4().hex)
    try:
        temporary.symlink_to(target)
        os.replace(temporary, CURRENT)
    finally:
        temporary.unlink(missing_ok=True)


def prepare():
    candidate = ROOT / '.venvs' / ('pi-' + uuid.uuid4().hex)
    candidate.parent.mkdir(exist_ok=True)
    run(sys.executable, '-m', 'venv', candidate)
    run(candidate / 'bin/python', '-m', 'pip', '--isolated', 'install',
        '--require-hashes', '--only-binary=:all:', '-r', LOCK)
    run(candidate / 'bin/python', '-m', 'pip', 'check')
    smoke(candidate)
    (candidate / 'piframe-ready.json').write_text(json.dumps({'lock_sha256': lock_hash()}))
    print(f'Prepared {candidate}\nActivate: {sys.executable} scripts/deploy_pi.py activate {candidate}')


def activate(candidate, allow_no_rollback=False):
    candidate = candidate.resolve(strict=True)
    if candidate.parent != (ROOT / '.venvs').resolve():
        raise RuntimeError('Candidate must be an environment prepared in .venvs')
    if json.loads((candidate / 'piframe-ready.json').read_text())['lock_sha256'] != lock_hash():
        raise RuntimeError('Dependency lock changed; prepare a new candidate')
    if CURRENT.exists() and not CURRENT.is_symlink():
        raise RuntimeError('venv-current must be a symlink')
    old = CURRENT.resolve(strict=True) if CURRENT.is_symlink() else ROOT / 'venv'
    command = subprocess.check_output(
        ['systemctl', 'show', 'piframe.service', '-p', 'ExecStart', '--value'], text=True)
    if f'path={ROOT}/scripts/start.sh ;' not in command:
        raise RuntimeError('Existing service must execute this checkout scripts/start.sh')
    # An OS upgrade can leave a Python 3.11 environment present but unusable.
    # Do not promise rollback unless its interpreter and native imports still work.
    rollback_ready = False
    try:
        if not (old / 'bin/python').exists():
            raise RuntimeError('No previous environment for rollback')
        smoke(old)
        rollback_ready = True
    except (RuntimeError, OSError, subprocess.CalledProcessError):
        if not allow_no_rollback:
            raise RuntimeError('Previous environment is unusable; restore it or explicitly '
                               'activate with --allow-no-rollback after an OS migration') from None
        print('WARNING: no working environment rollback; keep an SD-card backup', file=sys.stderr)
    smoke(candidate)
    try:
        switch(candidate)
        run('sudo', 'systemctl', 'restart', 'piframe.service')
        # Every probe has a network deadline; allow slow ARMv6 startup.
        for attempt in range(6):
            try:
                run("systemctl", "is-active", "--quiet", "piframe.service")
                smoke(candidate, live=True)
                break
            except subprocess.CalledProcessError:
                if attempt == 5:
                    raise
                time.sleep(5)
    except BaseException:
        if rollback_ready:
            switch(old)
            run('sudo', 'systemctl', 'restart', 'piframe.service')
            print('Activation failed; previous environment restored', file=sys.stderr)
        else:
            run('sudo', 'systemctl', 'stop', 'piframe.service')
            print('Activation failed; service stopped, candidate retained; '
                  'no working rollback environment', file=sys.stderr)
        raise
    print(f'Activated {candidate}; rollback target: {old if rollback_ready else "unavailable"}')


def main():
    global LOCK
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'activate'])
    parser.add_argument('candidate', nargs='?', type=Path)
    parser.add_argument('--allow-no-rollback', action='store_true',
                        help='Allow activation after an OS migration with no usable old environment')
    args = parser.parse_args()
    profile = check_target()
    LOCK = ROOT / f'requirements-pi-{profile}.txt'
    if args.action == 'prepare':
        prepare()
    elif args.candidate:
        activate(args.candidate, allow_no_rollback=args.allow_no_rollback)
    else:
        parser.error('activate requires the printed candidate path')


if __name__ == '__main__':
    main()
