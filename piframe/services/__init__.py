"""Service layer for PiFrame application.

Service classes are loaded lazily so importing one service module does not pull
in every optional dependency used by the others.
"""

__all__ = ['WeatherService', 'DriveService', 'ImageService']

_SERVICE_MODULES = {
    'WeatherService': '.weather_service',
    'DriveService': '.drive_service',
    'ImageService': '.image_service',
}


def __getattr__(name):
    """Load service classes on demand for backwards-compatible package imports."""
    if name not in _SERVICE_MODULES:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    from importlib import import_module

    module = import_module(_SERVICE_MODULES[name], __name__)
    service_class = getattr(module, name)
    globals()[name] = service_class
    return service_class
