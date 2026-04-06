# Changelog

## [2.0.0] - 2026-04-05

### Breaking Changes

- **Timer entity changed from Select to Number.** The timer is now a `NumberEntity` with a 1-240 minute range (step 1) instead of a `SelectEntity` with fixed 30-minute increments. Existing entity customizations (name overrides, area assignments) are preserved automatically via unchanged unique IDs.
- **Quickstart service `timer` parameter changed from string to integer.** The `timer` parameter now accepts an integer (minutes) instead of a string label. For example, `timer: "1 hour"` becomes `timer: 60`. Automations calling `beurer_cosynight.quickstart` with the old string format will need to be updated.

### Added

- `RestoreEntity` support for the timer -- last-set value persists across HA restarts

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

[2.0.0]: https://github.com/damonkohler/home-assistant-beurer-cosynight/releases/tag/v2.0.0
[1.1.0]: https://github.com/damonkohler/home-assistant-beurer-cosynight/releases/tag/v1.1.0
[1.0.0]: https://github.com/damonkohler/home-assistant-beurer-cosynight/releases/tag/v1.0.0
