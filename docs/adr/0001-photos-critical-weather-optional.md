# ADR 0001: Photos Are Critical, Weather Is Optional

## Status

Accepted

## Date

2026-06-14

## Context

PiFrame is primarily a digital photo frame. The README describes weather and
forecast information as useful companion features, but the core user promise is
that the frame displays memories from Google Drive.

Before this decision, the `/picture` route depended on current weather data.
When OpenWeatherMap was unconfigured, unavailable, or returned malformed data,
`/picture` returned `503`. Because `/fullscreen` embeds `/picture`, optional
weather failure could take down the primary frame experience.

The team review converged on the same principle:

- Karen, the target user, needs the household display to keep showing photos
  without requiring log inspection or developer troubleshooting.
- Paul, the PM, framed the near-term product direction as "Always-On Frame
  Reliability + Simple Diagnostics."
- Petr, the architect, called for explicit startup behavior and clear runtime
  degradation boundaries.
- Jiri, the developer, found that CLI startup validated config but ignored the
  failure result.
- Vishna, QA, identified weatherless `/picture` rendering and stuck image
  loading states as high-risk user flows.

## Decision

The photo frame route treats weather as an optional overlay:

- `/picture` renders successfully when weather data is missing or malformed.
- Weather UI is hidden on `/picture` when weather is unavailable.
- `/weather` remains strict and may return `503`, because weather is the whole
  purpose of that route.
- Client refresh timing in `/picture` uses `frontend_refresh_interval` from
  configuration instead of a hardcoded interval.
- Image loading success is tied to the browser image `onload` event. Image
  failures retry and then restore the previous photo where possible.
- CLI startup now stops when critical configuration validation fails.
- `/status` provides a local diagnostics snapshot without calling external APIs
  or exposing secrets.

## Consequences

Positive:

- The frame keeps its core promise during optional weather outages.
- Setup and runtime problems are easier to diagnose locally.
- Tests now pin the distinction between critical photo flow and optional
  weather overlay.
- The browser is less likely to remain stuck on an indefinite loading state.

Tradeoffs:

- `/picture` can render without weather information, so users may not see an
  explicit weather outage unless they check `/status` or `/weather`.
- `/status` is intentionally lightweight and cache/config based; it does not
  prove live Google Drive or OpenWeather reachability on every request.
- The current metadata synchronization model is still process-local and can be
  improved in a later iteration for multiple concurrent clients.

## Follow-Ups

- Add a browser smoke test for `/picture` image success and image failure.
- Add a fixture-backed metadata/image synchronization test.
- Decide whether `/status` should also have an HTML view for non-technical
  household troubleshooting.
- Clean up import-time app creation and service import boundaries.
- Fix first-run setup drift around credential file paths and helper scripts.
