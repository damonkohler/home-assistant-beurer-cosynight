"""Tests for Beurer CosyNight integration setup and unload."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import requests

from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from custom_components.beurer_cosynight import (
    PLATFORMS,
    _create_and_authenticate,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.beurer_cosynight.beurer_cosynight import (
    BeurerCosyNight,
    Device,
)
from custom_components.beurer_cosynight.const import DOMAIN

from .conftest import (
    MOCK_DEVICE_ID,
    MOCK_DEVICE_NAME,
    MOCK_ENTRY_ID,
    MOCK_PASSWORD,
    MOCK_USERNAME,
)


@pytest.fixture
def mock_entry():
    """Return a mock config entry."""
    entry = MagicMock()
    entry.data = {"username": MOCK_USERNAME, "password": MOCK_PASSWORD}
    entry.entry_id = MOCK_ENTRY_ID
    return entry


class TestCreateAndAuthenticate:
    """Test the _create_and_authenticate helper."""

    def test_creates_hub_authenticates_and_lists_devices(self, tmp_path):
        """Should create hub, authenticate, and list devices."""
        with patch(
            "custom_components.beurer_cosynight.BeurerCosyNight"
        ) as MockHub:
            mock_hub = MockHub.return_value
            mock_hub.list_devices.return_value = [
                Device(active=True, id="d1", name="Pad", requiresUpdate=False)
            ]

            hub, devices = _create_and_authenticate(
                str(tmp_path / "token"), MOCK_USERNAME, MOCK_PASSWORD
            )

        MockHub.assert_called_once_with(
            token_path=str(tmp_path / "token"),
            username=MOCK_USERNAME,
            password=MOCK_PASSWORD,
        )
        mock_hub.authenticate.assert_called_once_with(MOCK_USERNAME, MOCK_PASSWORD)
        mock_hub.list_devices.assert_called_once()
        assert len(devices) == 1

    def test_propagates_http_error(self, tmp_path):
        """HTTP errors should propagate for async_setup_entry to handle."""
        with patch(
            "custom_components.beurer_cosynight.BeurerCosyNight"
        ) as MockHub:
            MockHub.return_value.authenticate.side_effect = requests.HTTPError(
                response=MagicMock(status_code=401)
            )
            with pytest.raises(requests.HTTPError):
                _create_and_authenticate(
                    str(tmp_path / "token"), MOCK_USERNAME, MOCK_PASSWORD
                )

    def test_propagates_connection_error(self, tmp_path):
        """Connection errors should propagate."""
        with patch(
            "custom_components.beurer_cosynight.BeurerCosyNight"
        ) as MockHub:
            MockHub.return_value.authenticate.side_effect = (
                requests.ConnectionError("no network")
            )
            with pytest.raises(requests.ConnectionError):
                _create_and_authenticate(
                    str(tmp_path / "token"), MOCK_USERNAME, MOCK_PASSWORD
                )


class TestAsyncSetupEntry:
    """Test async_setup_entry error handling."""

    @pytest.mark.asyncio
    async def test_auth_failure_raises_config_entry_auth_failed(
        self, mock_hass, mock_entry
    ):
        """401/403 from API should raise ConfigEntryAuthFailed."""
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch(
            "custom_components.beurer_cosynight._create_and_authenticate",
            side_effect=requests.HTTPError(response=mock_response),
        ):
            with pytest.raises(ConfigEntryAuthFailed):
                await async_setup_entry(mock_hass, mock_entry)

    @pytest.mark.asyncio
    async def test_403_raises_config_entry_auth_failed(
        self, mock_hass, mock_entry
    ):
        """403 from API should also raise ConfigEntryAuthFailed."""
        mock_response = MagicMock()
        mock_response.status_code = 403

        with patch(
            "custom_components.beurer_cosynight._create_and_authenticate",
            side_effect=requests.HTTPError(response=mock_response),
        ):
            with pytest.raises(ConfigEntryAuthFailed):
                await async_setup_entry(mock_hass, mock_entry)

    @pytest.mark.asyncio
    async def test_network_error_raises_config_entry_not_ready(
        self, mock_hass, mock_entry
    ):
        """Network errors should raise ConfigEntryNotReady."""
        with patch(
            "custom_components.beurer_cosynight._create_and_authenticate",
            side_effect=requests.ConnectionError("no network"),
        ):
            with pytest.raises(ConfigEntryNotReady):
                await async_setup_entry(mock_hass, mock_entry)

    @pytest.mark.asyncio
    async def test_timeout_raises_config_entry_not_ready(
        self, mock_hass, mock_entry
    ):
        """Timeout should raise ConfigEntryNotReady."""
        with patch(
            "custom_components.beurer_cosynight._create_and_authenticate",
            side_effect=requests.Timeout("timed out"),
        ):
            with pytest.raises(ConfigEntryNotReady):
                await async_setup_entry(mock_hass, mock_entry)

    @pytest.mark.asyncio
    async def test_500_raises_config_entry_not_ready(
        self, mock_hass, mock_entry
    ):
        """Non-auth HTTP error (500) should raise ConfigEntryNotReady."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch(
            "custom_components.beurer_cosynight._create_and_authenticate",
            side_effect=requests.HTTPError(response=mock_response),
        ):
            with pytest.raises(ConfigEntryNotReady):
                await async_setup_entry(mock_hass, mock_entry)


class TestPlatforms:
    """Test platform configuration."""

    def test_platforms_include_select_sensor_button(self):
        """Integration should forward to select, sensor, and button platforms."""
        from homeassistant.const import Platform

        assert Platform.SELECT in PLATFORMS
        assert Platform.SENSOR in PLATFORMS
        assert Platform.BUTTON in PLATFORMS
        assert len(PLATFORMS) == 3
