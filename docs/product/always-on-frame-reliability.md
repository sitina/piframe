# Always-On Frame Reliability Iteration

## Date

2026-06-14

## Team Inputs

Karen, target user:
PiFrame should be a living-room or kitchen object that quietly shows family
memories. Setup and troubleshooting are the biggest sources of user friction.
If weather fails, the frame should still feel alive.

Paul, PM:
The near-term product direction is "Always-On Frame Reliability + Simple
Diagnostics." Defer larger controls, multi-album management, and dashboard work
until the primary frame experience is harder to break.

Jiri, developer:
The smallest high-impact code fix was to stop ignoring config validation in
CLI startup. That makes critical setup problems fail clearly instead of
booting into a broken app.

Petr, software architect:
Keep the iteration focused. Improve explicit startup behavior and runtime
degradation rules without starting a broad service-boundary refactor.

Vishna, QA:
The riskiest flows were weather taking down `/picture`, duplicated refresh
timing, and image loading failures leaving the UI stuck. Automatable follow-ups
should include browser smoke tests and fixture-backed sync tests.

## Scope Shipped

- `/picture` renders with photos even when weather is missing or malformed.
- Weather overlay sections are hidden when weather is unavailable.
- `/weather` remains the weather-specific failure surface.
- `/picture` uses the configured `frontend_refresh_interval`.
- Image load completion now waits for the actual image `onload`.
- Image load failures retry and restore the previous image when possible.
- CLI startup returns failure when critical config validation fails.
- `/status` returns safe local diagnostics for photo setup, weather config,
  cache state, background tasks, and selected runtime config.
- Unit/integration tests cover weatherless photo rendering, malformed weather
  fallback, startup validation failure, status output, and refresh interval
  propagation.

## Acceptance Criteria

- With no weather API key, `/picture` returns `200` and can display photos.
- If weather data is malformed, `/picture` still renders a photo view.
- `/weather` returns `503` when weather data is unavailable.
- Failed image loads do not leave the frame in an infinite loading state.
- The photo refresh interval comes from configuration.
- Startup stops before running the server when critical config validation fails.
- `/status` does not expose API keys, OAuth tokens, or credential contents.
- The broad local test runner passes.

## Verified

Command:

```bash
MPLCONFIGDIR=/private/tmp/piframe-mpl /private/tmp/piframe-testvenv/bin/python scripts/run_tests.py --unit-only
```

Result:

```text
Ran 227 tests in 4.961s
OK
```

## Deferred Backlog

- Add browser automation for `/picture` success, failed image loading, and
  fullscreen iframe refresh behavior.
- Add a fixture-backed metadata/image synchronization test with real JPEG bytes.
- Add a two-client synchronization race test.
- Clean up import-time Flask app creation and eager service imports.
- Fix setup/documentation drift:
  - `setup.py` should use `config/client_secret.json`.
  - `scripts/test_drive_connection.py` should use the current `DriveService`
    API.
  - systemd docs should point to existing scripts.
- Consider an HTML diagnostics page for household use.
