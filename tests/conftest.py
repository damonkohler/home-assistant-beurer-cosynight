"""Shared fixtures for Beurer CosyNight tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.beurer_cosynight.beurer_cosynight import (
    BeurerCosyNight,
    Device,
    Status,
)

MOCK_USERNAME = "test@example.com"
MOCK_PASSWORD = "testpass123"
MOCK_DEVICE_ID = "device-abc-123"
MOCK_DEVICE_NAME = "My Mattress Pad"
MOCK_ENTRY_ID = "test_entry_id_123"


@pytest.fixture
def mock_device() -> Device:
    """Return a mock Device."""
    return Device(
        active=True,
        id=MOCK_DEVICE_ID,
        name=MOCK_DEVICE_NAME,
        requiresUpdate=False,
    )


@pytest.fixture
def mock_status() -> Status:
    """Return a mock Status."""
    return Status(
        active=True,
        bodySetting=3,
        feetSetting=5,
        heartbeat=100,
        id=MOCK_DEVICE_ID,
        name=MOCK_DEVICE_NAME,
        requiresUpdate=False,
        timer=1800,
    )


@pytest.fixture
def mock_hass(tmp_path):
    """Return a lightweight mock HomeAssistant."""
    hass = MagicMock()
    hass.config.path.return_value = str(tmp_path / ".storage" / "beurer_token")
    hass.data = {}
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    return hass


# ---------------------------------------------------------------------------
# Test infrastructure
# ---------------------------------------------------------------------------


class FakeHttpClient:
    """Test double for HttpClient protocol.

    Queues responses and records requests for assertions.
    """

    def __init__(self, responses: list[dict | Exception] | None = None) -> None:
        self.responses: list[dict | Exception] = list(responses or [])
        self.requests: list[tuple[str, str, dict]] = []
        self.closed = False

    def add_response(self, body: dict) -> None:
        """Queue a successful JSON response."""
        self.responses.append(body)

    def add_error(self, error: Exception) -> None:
        """Queue an error to be raised."""
        self.responses.append(error)

    def _next_response(self) -> dict:
        if not self.responses:
            raise RuntimeError("FakeHttpClient: no more queued responses")
        resp = self.responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp

    async def get(
        self,
        url: str,
        *,
        headers: dict | None = None,
        timeout: float | None = None,
    ) -> dict:
        self.requests.append(("GET", url, {"headers": headers, "timeout": timeout}))
        return self._next_response()

    async def post(
        self,
        url: str,
        *,
        data: dict | None = None,
        json: dict | None = None,
        headers: dict | None = None,
        timeout: float | None = None,
    ) -> dict:
        self.requests.append(
            (
                "POST",
                url,
                {"data": data, "json": json, "headers": headers, "timeout": timeout},
            )
        )
        return self._next_response()

    async def close(self) -> None:
        self.closed = True


@pytest.fixture
def fake_http_client():
    """Return a fresh FakeHttpClient."""
    return FakeHttpClient()


@pytest.fixture
def mock_hub_async(mock_device, mock_status) -> AsyncMock:
    """Return an async mock BeurerCosyNight hub for post-migration tests."""
    hub = AsyncMock(spec=BeurerCosyNight)
    hub.authenticate.return_value = None
    hub.list_devices.return_value = [mock_device]
    hub.get_status.return_value = mock_status
    hub.quickstart.return_value = mock_status
    return hub
