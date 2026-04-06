# Beurer CosyNight Test Suite

## Setup

```bash
cd /home/claude/haos-config/repos/home-assistant-beurer-cosynight
python -m venv venv
venv/bin/pip install -r requirements-dev.txt
```

## Running Tests

```bash
# All tests
PYTHONPATH=. ./venv/bin/python -m pytest tests/ -v

# Single file
PYTHONPATH=. ./venv/bin/python -m pytest tests/test_number.py -v

# Single test
PYTHONPATH=. ./venv/bin/python -m pytest tests/test_number.py::TestTimerNumber::test_default_value -v

# With coverage
PYTHONPATH=. ./venv/bin/python -m pytest tests/ --cov=custom_components/beurer_cosynight --cov-report=term-missing -v

# Stop on first failure
PYTHONPATH=. ./venv/bin/python -m pytest tests/ -x -v
```

## Test Structure

| File | Module Under Test | Description |
|---|---|---|
| `conftest.py` | -- | Shared fixtures: `mock_hass`, `mock_hub_async`, `FakeHttpClient`, mock constants |
| `test_api_client.py` | `beurer_cosynight.py` | Dataclass fields (`Device`, `Status`, `Quickstart`) |
| `test_api_client_async.py` | `beurer_cosynight.py` | Async API client: auth, token persistence/refresh, get_status, list_devices, quickstart, error hierarchy |
| `test_button.py` | `button.py` | `StopButton` entity: press sends quickstart with zeros, error handling, entity metadata |
| `test_config_flow.py` | `config_flow.py` | Config flow: user step (auth success/failure), reauth flow, flow metadata |
| `test_coordinator.py` | `coordinator.py` | Coordinator: update interval, data fetching, error mapping, quickstart lock |
| `test_http_client.py` | `conftest.py` | `FakeHttpClient` test double: protocol conformance, request recording, response queuing |
| `test_init.py` | `__init__.py` | Integration setup/unload, quickstart service handler, schema validation, platform list |
| `test_number.py` | `number.py` | `TimerNumber` entity: range/step/mode/unit, timespan conversion, state restoration, platform setup |
| `test_select.py` | `select.py` | `BodyZone`/`FeetZone` entities: option reading, quickstart dispatch, lock serialization, TOCTOU race prevention |
| `test_sensor.py` | `sensor.py` | `DeviceTimerSensor` entity: native_value from coordinator, device class, platform setup |

## Conventions

- **Async tests**: All async tests use `pytest-asyncio` with `asyncio_mode = "auto"` (no explicit `@pytest.mark.asyncio` needed).
- **Mocking style**: `from unittest.mock import AsyncMock, MagicMock, patch` (direct imports).
- **Fixtures**: Shared fixtures live in `conftest.py`. Per-file fixtures are defined at the top of each test file.
- **Test doubles**: `FakeHttpClient` (protocol boundary stub) for the HTTP layer. Mock coordinators with real `asyncio.Lock` for concurrency tests.
- **Assertions**: Tests assert on behavioral outcomes (return values, side effects, state changes), not internal wiring.
