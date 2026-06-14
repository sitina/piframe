# ADR 0002: Keep Imports Side-Effect Light

## Status

Accepted

## Date

2026-06-14

## Context

PiFrame supports multiple entry points:

- `python app.py` for the normal CLI/server startup path.
- Flask's application factory discovery through `create_app()`.
- Tests and maintenance scripts that import modules directly.

Previously, importing `app.py` also created a Flask application through a
module-level `app = create_app(...)`. That meant import-time code could load
configuration, mutate logging handlers, initialize caches, and construct
services before the caller explicitly asked for an application.

The service package had a similar issue: `import piframe.services` imported
weather, Drive, and image services at once. This pulled chart-rendering and
Google API dependencies into paths that did not need them.

## Decision

Imports should define names and lightweight helpers only. Runtime composition
belongs behind explicit factory or constructor calls.

Concretely:

- `app.py` no longer exposes a module-level Flask `app`.
- `create_app()` is the Flask application factory.
- `main()` remains the `python app.py` CLI entry point.
- `PiFrameApp` creates services through `create_services()` so service modules
  are imported only when an application instance is being composed.
- `piframe.services` keeps backwards-compatible package exports, but resolves
  service classes lazily through `__getattr__`.
- `weather_service` loads Matplotlib only when forecast chart rendering is
  requested.
- `image_service` keeps the Drive service import type-only, avoiding runtime
  coupling for annotations.

## Consequences

Positive:

- `import app` no longer creates config files, config objects, caches, services,
  background tasks, or logging side effects.
- Tests can import app symbols without paying the cost of service construction.
- Importing the Drive service no longer imports weather or chart dependencies.
- Weather API methods do not import Matplotlib unless a chart is rendered.
- The import boundary is now pinned by dedicated tests.

Tradeoffs:

- Consumers that relied on `app:app`, `from app import app`, or
  `gunicorn app:app` must switch to the application factory style, such as
  `app:create_app()` or an explicit WSGI wrapper outside `app.py`.
- A WSGI module that creates `app = create_app()` is still valid, but importing
  that WSGI module is intentionally an application-construction action.
- `create_app()` still loads runtime configuration and configures logging for
  Flask factory use. A future cleanup can separate reusable factory behavior
  from CLI logging policy more strictly.

## Verification

Commands:

```bash
MPLCONFIGDIR=/private/tmp/piframe-mpl /private/tmp/piframe-testvenv/bin/python -m unittest tests.test_import_boundaries tests.test_app tests.test_weather_service tests.test_image_service -v
MPLCONFIGDIR=/private/tmp/piframe-mpl /private/tmp/piframe-testvenv/bin/python scripts/run_tests.py --unit-only
```

Results:

```text
Ran 105 tests in 0.830s
OK

Ran 231 tests in 5.152s
OK
```

Smoke import:

```bash
/private/tmp/piframe-testvenv/bin/python -c "import app, sys; print(hasattr(app, 'app')); print('piframe.services.weather_service' in sys.modules); print('matplotlib' in sys.modules)"
```

Result:

```text
False
False
False
```

## Follow-Ups

- Split `create_app()` logging setup from reusable application creation.
- Decide whether to add a documented deployment `wsgi.py` template that makes
  application construction explicit.
- Make `Config.load()` file creation opt-in so setup remains the only path that
  writes default config files.
- Guard background tasks when Flask debug reloader is enabled.
