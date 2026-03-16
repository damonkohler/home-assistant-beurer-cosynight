"""Beurer CosyNight integration."""

from __future__ import annotations

import logging

import requests

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .beurer_cosynight import BeurerCosyNight
from .const import DOMAIN
from .coordinator import BeurerCosyNightCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SELECT, Platform.SENSOR, Platform.BUTTON]


def _create_and_authenticate(
    token_path: str, username: str, password: str
) -> tuple[BeurerCosyNight, list]:
    """Create hub, authenticate, and list devices (runs in executor)."""
    hub = BeurerCosyNight(token_path=token_path, username=username, password=password)
    hub.authenticate(username, password)
    devices = hub.list_devices()
    return hub, devices


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Beurer CosyNight from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    token_path = hass.config.path(f".storage/beurer_cosynight_{entry.entry_id}")

    try:
        hub, devices = await hass.async_add_executor_job(
            _create_and_authenticate, token_path, username, password
        )
    except requests.HTTPError as err:
        if err.response is not None and err.response.status_code in (401, 403):
            raise ConfigEntryAuthFailed("Invalid credentials") from err
        raise ConfigEntryNotReady(f"Error communicating with API: {err}") from err
    except requests.RequestException as err:
        raise ConfigEntryNotReady(f"Error communicating with API: {err}") from err

    if not devices:
        _LOGGER.warning("No Beurer CosyNight devices found")

    coordinators: dict[str, BeurerCosyNightCoordinator] = {}
    for device in devices:
        coordinator = BeurerCosyNightCoordinator(hass, hub, device.id, device.name)
        await coordinator.async_config_entry_first_refresh()
        coordinators[device.id] = coordinator

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "hub": hub,
        "devices": devices,
        "coordinators": coordinators,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
        return True
    return False
