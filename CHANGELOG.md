# Changelog

## [1.1.0] - 2026-04-05

### Added

- Reauth flow -- re-authenticate directly from the HA UI when credentials expire
- `beurer_cosynight.quickstart` service for automation and script use, with lock serialization

### Fixed

- TOCTOU race: read coordinator state inside lock in select entity
- Proactive token refresh and retry on auth failure
- Type annotations for zone constructors and `HttpClient` protocol

### Changed

- Migrated from `requests` to `aiohttp` for native async HTTP
- Extracted `QUICKSTART_SCHEMA` to module level
- Added pre-commit hooks
- Replaced fragile zone-label test heuristic with call counter
- Code quality improvements

## [1.0.0] - 2026-03-22

Initial release.

- Config flow setup via the HA UI
- Auto-discovers all mattress pads linked to your Beurer account
- Per-device controls: body zone (0-9), feet zone (0-9), timer, stop button, and remaining time sensor
- `beurer_cosynight.quickstart` service for automation and script use

[1.1.0]: https://github.com/damonkohler/home-assistant-beurer-cosynight/releases/tag/v1.1.0
[1.0.0]: https://github.com/damonkohler/home-assistant-beurer-cosynight/releases/tag/v1.0.0
