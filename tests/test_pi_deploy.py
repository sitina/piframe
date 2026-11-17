import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path('scripts') / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestPiDeploy(unittest.TestCase):
    def setUp(self):
        self.module = load('deploy_pi')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.module.ROOT = self.root
        self.module.CURRENT = self.root / 'venv-current'
        self.module.LOCK = self.root / 'requirements-pi-bookworm.txt'
        self.module.LOCK.write_text('fixture lock')
        self.old = self.root / 'venv'
        (self.old / 'bin').mkdir(parents=True)
        (self.old / 'bin/python').touch()
        self.candidate = self.root / '.venvs/pi-test'
        self.candidate.mkdir(parents=True)
        (self.candidate / 'piframe-ready.json').write_text(json.dumps(
            {'lock_sha256': self.module.lock_hash()}))

    def activate(self):
        with patch.object(self.module.subprocess, 'check_output', return_value=
                          f'{{ path={self.root}/scripts/start.sh ; argv[]=... }}'), \
                patch.object(self.module, 'run'), patch.object(self.module.time, 'sleep'):
            self.module.activate(self.candidate)

    def test_activation_switches_without_moving_candidate(self):
        with patch.object(self.module, 'smoke') as smoke:
            self.activate()
        self.assertEqual(self.module.CURRENT.resolve(), self.candidate)
        self.assertTrue(self.candidate.exists())
        self.assertEqual(smoke.call_count, 3)

    def test_failed_photo_probe_restores_old_environment(self):
        failure = subprocess.CalledProcessError(1, 'smoke')
        with patch.object(self.module, 'smoke', side_effect=[None, None] + [failure] * 6):
            with self.assertRaises(subprocess.CalledProcessError):
                self.activate()
        self.assertEqual(self.module.CURRENT.resolve(), self.old)

    def test_lock_drift_rejects_before_switch(self):
        self.module.LOCK.write_text('changed')
        with self.assertRaises(RuntimeError):
            self.activate()
        self.assertFalse(self.module.CURRENT.exists())

    def test_wrong_target_is_rejected(self):
        with patch.object(self.module.platform, 'machine', return_value='aarch64'):
            with self.assertRaises(RuntimeError):
                self.module.check_target()

    def test_supported_os_and_python_pairs(self):
        for release, python, profile in [('12', (3, 11), 'bookworm'),
                                         ('13', (3, 13), 'trixie')]:
            with self.subTest(profile=profile), \
                    patch.object(self.module.platform, 'machine', return_value='armv6l'), \
                    patch.object(self.module.struct, 'calcsize', return_value=4), \
                    patch.object(self.module.platform, 'freedesktop_os_release',
                                 return_value={'ID': 'raspbian', 'VERSION_ID': release}), \
                    patch.object(self.module.sys, 'version_info', python):
                self.assertEqual(self.module.check_target(), profile)
                with patch.object(self.module.sys, 'version_info', (3, 12)):
                    with self.assertRaises(RuntimeError):
                        self.module.check_target()

    def test_broken_old_environment_rejects_before_switch(self):
        with patch.object(self.module, 'smoke', side_effect=OSError('missing interpreter')):
            with self.assertRaisesRegex(RuntimeError, 'Previous environment is unusable'):
                self.activate()
        self.assertFalse(self.module.CURRENT.exists())

    def test_explicit_migration_failure_stops_service_without_claiming_rollback(self):
        failure = subprocess.CalledProcessError(1, 'smoke')
        with patch.object(self.module.subprocess, 'check_output', return_value=
                          f'{{ path={self.root}/scripts/start.sh ; argv[]=... }}'), \
                patch.object(self.module, 'run') as run, \
                patch.object(self.module.time, 'sleep'), \
                patch.object(self.module, 'smoke', side_effect=[failure, None] + [failure] * 6):
            with self.assertRaises(subprocess.CalledProcessError):
                self.module.activate(self.candidate, allow_no_rollback=True)
        self.assertEqual(run.call_args.args, ('sudo', 'systemctl', 'stop', 'piframe.service'))
        self.assertTrue(self.candidate.exists())

    def test_native_manifest_matches_target_lock(self):
        for profile in ['bookworm', 'trixie']:
            manifest = json.loads(Path(f'deployment/pi-{profile}-artifacts.json').read_text())
            lock = Path(f'requirements-pi-{profile}.txt').read_text()
            for item in manifest['artifacts'].values():
                self.assertIn(item['url'], lock)
                self.assertIn('--hash=sha256:' + item['sha256'], lock)
                self.assertTrue(set(item['apt_dependencies']) <= set(manifest['apt_packages']))


class TestPiLocks(unittest.TestCase):
    def test_generation_reproduces_each_profile_and_rejects_wrong_abi(self):
        module = load('lock_pi')
        for profile in ['bookworm', 'trixie']:
            with self.subTest(profile=profile):
                manifest = json.loads(Path(f'deployment/pi-{profile}-artifacts.json').read_text())

                def fetch(name):
                    item = manifest['artifacts'][name]
                    return {'releases': {item['version']: {'files': {
                        item['url'].rsplit('/', 1)[1]: {
                            'file_url': item['url'], 'filehash': item['sha256'],
                            'apt_dependencies': item['apt_dependencies']}}}}}

                lock, apt, artifacts = module.generate(fetch, profile)
                self.assertEqual(lock, Path(f'requirements-pi-{profile}.txt').read_text())
                self.assertEqual(apt, manifest['apt_packages'])
                self.assertEqual(artifacts, manifest['artifacts'])
                other = 'trixie' if profile == 'bookworm' else 'bookworm'
                with self.assertRaisesRegex(ValueError, 'ARMv6 artifact'):
                    module.generate(fetch, other)
