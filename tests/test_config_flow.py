"""Tests for the Beurer CosyNight config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import requests

from custom_components.beurer_cosynight.config_flow import (
    BeurerCosyNightConfigFlow,
    _test_credentials,
)
from custom_components.beurer_cosynight.const import DOMAIN


@pytest.fixture
def flow(mock_hass):
    """Return a config flow instance with mock hass."""
    flow = BeurerCosyNightConfigFlow()
    flow.hass = mock_hass
    return flow


class TestConfigFlowUserStep:
    """Test the user step of the config flow."""

    @pytest.mark.asyncio
    async def test_show_form_when_no_input(self, flow):
        """No user_input shows the form."""
        result = await flow.async_step_user(user_input=None)

        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert result["errors"] == {}

    @pytest.mark.asyncio
    async def test_successful_auth_creates_entry(self, flow):
        """Successful authentication creates a config entry."""
        with patch(
            "custom_components.beurer_cosynight.config_flow._test_credentials",
            return_value=None,
        ), patch.object(flow, "async_set_unique_id", new_callable=AsyncMock), \
           patch.object(flow, "_abort_if_unique_id_configured"):
            result = await flow.async_step_user(
                user_input={"username": "test@example.com", "password": "pass123"}
            )

        assert result["type"] == "create_entry"
        assert result["title"] == "Beurer CosyNight (test@example.com)"
        assert result["data"] == {
            "username": "test@example.com",
            "password": "pass123",
        }

    @pytest.mark.asyncio
    async def test_invalid_auth_on_401(self, flow):
        """HTTP 401 should show invalid_auth error."""
        mock_response = requests.Response()
        mock_response.status_code = 401

        with patch(
            "custom_components.beurer_cosynight.config_flow._test_credentials",
            side_effect=requests.HTTPError(response=mock_response),
        ):
            result = await flow.async_step_user(
                user_input={"username": "bad@example.com", "password": "wrong"}
            )

        assert result["type"] == "form"
        assert result["errors"] == {"base": "invalid_auth"}

    @pytest.mark.asyncio
    async def test_invalid_auth_on_403(self, flow):
        """HTTP 403 should show invalid_auth error."""
        mock_response = requests.Response()
        mock_response.status_code = 403

        with patch(
            "custom_components.beurer_cosynight.config_flow._test_credentials",
            side_effect=requests.HTTPError(response=mock_response),
        ):
            result = await flow.async_step_user(
                user_input={"username": "bad@example.com", "password": "wrong"}
            )

        assert result["type"] == "form"
        assert result["errors"] == {"base": "invalid_auth"}

    @pytest.mark.asyncio
    async def test_cannot_connect_on_network_error(self, flow):
        """Network error should show cannot_connect."""
        with patch(
            "custom_components.beurer_cosynight.config_flow._test_credentials",
            side_effect=requests.ConnectionError("no network"),
        ):
            result = await flow.async_step_user(
                user_input={"username": "test@example.com", "password": "pass"}
            )

        assert result["type"] == "form"
        assert result["errors"] == {"base": "cannot_connect"}

    @pytest.mark.asyncio
    async def test_cannot_connect_on_timeout(self, flow):
        """Timeout should show cannot_connect."""
        with patch(
            "custom_components.beurer_cosynight.config_flow._test_credentials",
            side_effect=requests.Timeout("timed out"),
        ):
            result = await flow.async_step_user(
                user_input={"username": "test@example.com", "password": "pass"}
            )

        assert result["type"] == "form"
        assert result["errors"] == {"base": "cannot_connect"}

    @pytest.mark.asyncio
    async def test_cannot_connect_on_server_error(self, flow):
        """HTTP 500 should show cannot_connect (not invalid_auth)."""
        mock_response = requests.Response()
        mock_response.status_code = 500

        with patch(
            "custom_components.beurer_cosynight.config_flow._test_credentials",
            side_effect=requests.HTTPError(response=mock_response),
        ):
            result = await flow.async_step_user(
                user_input={"username": "test@example.com", "password": "pass"}
            )

        assert result["type"] == "form"
        assert result["errors"] == {"base": "cannot_connect"}

    @pytest.mark.asyncio
    async def test_unexpected_exception_maps_to_cannot_connect(self, flow):
        """Unexpected exceptions should show cannot_connect."""
        with patch(
            "custom_components.beurer_cosynight.config_flow._test_credentials",
            side_effect=RuntimeError("something weird"),
        ):
            result = await flow.async_step_user(
                user_input={"username": "test@example.com", "password": "pass"}
            )

        assert result["type"] == "form"
        assert result["errors"] == {"base": "cannot_connect"}


class TestTestCredentials:
    """Test the _test_credentials helper function."""

    def test_creates_hub_and_authenticates(self):
        """_test_credentials should create a BeurerCosyNight and call authenticate."""
        with patch(
            "custom_components.beurer_cosynight.config_flow.BeurerCosyNight"
        ) as MockHub:
            _test_credentials("user@test.com", "pass123")

        MockHub.assert_called_once()
        MockHub.return_value.authenticate.assert_called_once_with(
            "user@test.com", "pass123"
        )

    def test_propagates_http_error(self):
        """HTTP errors from authenticate should propagate."""
        with patch(
            "custom_components.beurer_cosynight.config_flow.BeurerCosyNight"
        ) as MockHub:
            MockHub.return_value.authenticate.side_effect = requests.HTTPError()
            with pytest.raises(requests.HTTPError):
                _test_credentials("user@test.com", "pass123")


class TestFlowMetadata:
    """Test config flow class metadata."""

    def test_domain(self):
        """Config flow should be registered for the correct domain."""
        # The domain is set via ConfigFlow(domain=DOMAIN) metaclass
        from homeassistant.config_entries import HANDLERS

        # Verify the flow handler is registered for our domain
        assert DOMAIN in HANDLERS

    def test_version(self):
        """Config flow version should be 1."""
        assert BeurerCosyNightConfigFlow.VERSION == 1
