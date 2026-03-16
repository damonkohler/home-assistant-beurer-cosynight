"""Config flow for Beurer CosyNight integration."""

from __future__ import annotations

import logging
from typing import Any

import os

import requests
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult

from .beurer_cosynight import BeurerCosyNight
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


def _test_credentials(username: str, password: str) -> None:
    """Test credentials by authenticating (runs in executor)."""
    hub = BeurerCosyNight(token_path=os.devnull)
    hub.authenticate(username, password)


class BeurerCosyNightConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Beurer CosyNight."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await self.hass.async_add_executor_job(
                    _test_credentials,
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
            except requests.HTTPError as err:
                if err.response is not None and err.response.status_code in (401, 403):
                    errors["base"] = "invalid_auth"
                else:
                    _LOGGER.exception("Failed to connect to Beurer CosyNight")
                    errors["base"] = "cannot_connect"
            except requests.RequestException:
                _LOGGER.exception("Failed to connect to Beurer CosyNight")
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during authentication")
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(user_input[CONF_USERNAME])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Beurer CosyNight ({user_input[CONF_USERNAME]})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
