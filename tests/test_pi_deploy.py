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
        self.assertEqual(smoke.call_count, 2)

    def test_failed_photo_probe_restores_old_environment(self):
        failure = subprocess.CalledProcessError(1, 'smoke')
        with patch.object(self.module, 'smoke', side_effect=[None] + [failure] * 6):
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

    def test_native_manifest_matches_target_lock(self):
        manifest = json.loads(Path('deployment/pi-bookworm-artifacts.json').read_text())
        lock = Path('requirements-pi-bookworm.txt').read_text()
        for item in manifest['artifacts'].values():
            self.assertIn(item['url'], lock)
            self.assertIn('--hash=sha256:' + item['sha256'], lock)
            self.assertTrue(set(item['apt_dependencies']) <= set(manifest['apt_packages']))
