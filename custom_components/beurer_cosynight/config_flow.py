"""Config flow for Beurer CosyNight integration."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .beurer_cosynight import AiohttpClient, ApiError, AuthError, BeurerCosyNight
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class BeurerCosyNightConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Beurer CosyNight."""

    VERSION = 1

    async def _validate_credentials(
        self, username: str, password: str
    ) -> dict[str, str]:
        """Validate credentials against the Beurer API.

        Returns a dict of errors (empty on success).
        """
        errors: dict[str, str] = {}
        try:
            session = async_get_clientsession(self.hass)
            client = AiohttpClient(session)
            hub = BeurerCosyNight(client, token_path=os.devnull)
            await hub.authenticate(username, password)
        except AuthError:
            errors["base"] = "invalid_auth"
        except ApiError:
            _LOGGER.exception("Failed to connect to Beurer CosyNight")
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected error during authentication")
            errors["base"] = "unknown"
        return errors

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = await self._validate_credentials(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            if not errors:
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

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reauth confirmation."""
        errors: dict[str, str] = {}

        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            errors = await self._validate_credentials(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            if not errors:
                await self.async_set_unique_id(user_input[CONF_USERNAME])
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data={
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_USERNAME,
                    default=reauth_entry.data.get(CONF_USERNAME, ""),
                ): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=schema,
            errors=errors,
            description_placeholders={"name": reauth_entry.title},
        )
