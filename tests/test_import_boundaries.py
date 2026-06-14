"""Tests for import-time boundaries and side effects."""

import importlib
import sys
import unittest
from unittest.mock import patch


class ModuleRestoreMixin:
    """Helpers for temporarily importing modules from a clean sys.modules state."""

    def _restore_modules(self, saved_modules):
        for name, module in saved_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


class TestAppImportBoundary(ModuleRestoreMixin, unittest.TestCase):
    """Tests for app module import behavior."""

    def test_importing_app_does_not_create_application(self):
        """Importing app should not load config or create services."""
        saved_modules = {
            'app': sys.modules.pop('app', None),
            'piframe.services.weather_service': sys.modules.pop(
                'piframe.services.weather_service', None
            ),
            'piframe.services.drive_service': sys.modules.pop(
                'piframe.services.drive_service', None
            ),
            'piframe.services.image_service': sys.modules.pop(
                'piframe.services.image_service', None
            ),
        }

        try:
            with patch('piframe.config.Config.load') as mock_config_load, \
                 patch('piframe.utils.setup_logging') as mock_setup_logging, \
                 patch('piframe.models.get_cache_manager') as mock_cache_manager:
                module = importlib.import_module('app')

            self.assertTrue(callable(module.create_app))
            self.assertFalse(hasattr(module, 'app'))
            self.assertNotIn('piframe.services.weather_service', sys.modules)
            self.assertNotIn('piframe.services.drive_service', sys.modules)
            self.assertNotIn('piframe.services.image_service', sys.modules)
            mock_config_load.assert_not_called()
            mock_setup_logging.assert_not_called()
            mock_cache_manager.assert_not_called()
        finally:
            self._restore_modules(saved_modules)


class TestServiceImportBoundary(ModuleRestoreMixin, unittest.TestCase):
    """Tests for service package import behavior."""

    def _pop_modules(self, predicate):
        saved_modules = {}
        for name in list(sys.modules):
            if predicate(name):
                saved_modules[name] = sys.modules.pop(name)
        return saved_modules

    def test_drive_service_import_does_not_import_weather_service(self):
        """The service package should load individual services on demand."""
        module_names = {
            'piframe.services': sys.modules.pop('piframe.services', None),
            'piframe.services.drive_service': sys.modules.pop(
                'piframe.services.drive_service', None
            ),
            'piframe.services.weather_service': sys.modules.pop(
                'piframe.services.weather_service', None
            ),
            'piframe.services.image_service': sys.modules.pop(
                'piframe.services.image_service', None
            ),
        }

        try:
            services = importlib.import_module('piframe.services')

            self.assertNotIn('piframe.services.drive_service', sys.modules)
            self.assertNotIn('piframe.services.weather_service', sys.modules)
            self.assertNotIn('piframe.services.image_service', sys.modules)

            drive_service_class = services.DriveService

            self.assertEqual(drive_service_class.__name__, 'DriveService')
            self.assertIn('piframe.services.drive_service', sys.modules)
            self.assertNotIn('piframe.services.weather_service', sys.modules)
            self.assertNotIn('piframe.services.image_service', sys.modules)
        finally:
            self._restore_modules(module_names)

    def test_weather_service_import_does_not_import_matplotlib(self):
        """Weather API access should not pay chart-rendering import cost."""
        saved_modules = self._pop_modules(
            lambda name: (
                name == 'piframe.services.weather_service'
                or name == 'matplotlib'
                or name.startswith('matplotlib.')
            )
        )

        try:
            module = importlib.import_module('piframe.services.weather_service')

            self.assertTrue(hasattr(module, 'WeatherService'))
            self.assertNotIn('matplotlib', sys.modules)
            self.assertFalse(
                any(name.startswith('matplotlib.') for name in sys.modules)
            )
        finally:
            self._restore_modules(saved_modules)

    def test_image_service_import_does_not_import_drive_service(self):
        """ImageService should not import DriveService only for annotations."""
        saved_modules = {
            'piframe.services.image_service': sys.modules.pop(
                'piframe.services.image_service', None
            ),
            'piframe.services.drive_service': sys.modules.pop(
                'piframe.services.drive_service', None
            ),
        }

        try:
            module = importlib.import_module('piframe.services.image_service')

            self.assertTrue(hasattr(module, 'ImageService'))
            self.assertNotIn('piframe.services.drive_service', sys.modules)
        finally:
            self._restore_modules(saved_modules)


if __name__ == '__main__':
    unittest.main()
