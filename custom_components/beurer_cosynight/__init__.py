"""Beurer CosyNight integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .beurer_cosynight import (
    AiohttpClient,
    ApiError,
    AuthError,
    BeurerCosyNight,
    Quickstart,
)
from .const import DEFAULT_TIMER_LABEL, DOMAIN, TIMER_OPTIONS
from .coordinator import BeurerCosyNightCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SELECT, Platform.SENSOR, Platform.BUTTON]

QUICKSTART_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): str,
        vol.Required("body"): vol.All(vol.Coerce(int), vol.Range(min=0, max=9)),
        vol.Required("feet"): vol.All(vol.Coerce(int), vol.Range(min=0, max=9)),
        vol.Optional("timer"): vol.In(TIMER_OPTIONS),
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Beurer CosyNight from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    token_path = hass.config.path(f".storage/beurer_cosynight_{entry.entry_id}")

    session = async_get_clientsession(hass)
    client = AiohttpClient(session)
    hub = BeurerCosyNight(
        client, token_path=token_path, username=username, password=password
    )

    try:
        await hub.authenticate(username, password)
        devices = await hub.list_devices()
    except AuthError as err:
        raise ConfigEntryAuthFailed("Invalid credentials") from err
    except ApiError as err:
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

    async def handle_quickstart(call: ServiceCall) -> None:
        """Handle the quickstart service call."""
        dev_reg = dr.async_get(hass)
        device_id = call.data["device_id"]
        device_entry = dev_reg.async_get(device_id)
        if device_entry is None:
            raise HomeAssistantError(f"Device {device_id} not found")

        # Find the Beurer device ID from the device registry.
        beurer_device_id: str | None = None
        for identifier in device_entry.identifiers:
            if identifier[0] == DOMAIN:
                beurer_device_id = identifier[1]
                break
        if beurer_device_id is None:
            raise HomeAssistantError(
                f"Device {device_id} is not a Beurer CosyNight device"
            )

        # Search all config entries for the coordinator.
        coordinator = None
        for entry_data in hass.data[DOMAIN].values():
            coordinator = entry_data["coordinators"].get(beurer_device_id)
            if coordinator is not None:
                break
        if coordinator is None:
            raise HomeAssistantError(f"No coordinator for device {beurer_device_id}")

        timer_label = call.data.get("timer", DEFAULT_TIMER_LABEL)
        timespan = TIMER_OPTIONS.get(timer_label, TIMER_OPTIONS[DEFAULT_TIMER_LABEL])

        async with coordinator.quickstart_lock:
            qs = Quickstart(
                bodySetting=int(call.data["body"]),
                feetSetting=int(call.data["feet"]),
                id=beurer_device_id,
                timespan=timespan,
            )
            try:
                await coordinator.hub.quickstart(qs)
            except AuthError as err:
                raise HomeAssistantError("Authentication failed") from err
            except ApiError as err:
                raise HomeAssistantError(f"API error: {err}") from err
            await coordinator.async_request_refresh()

    if not hass.services.has_service(DOMAIN, "quickstart"):
        hass.services.async_register(
            DOMAIN,
            "quickstart",
            handle_quickstart,
            schema=QUICKSTART_SCHEMA,
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, "quickstart")
        return True
    return False
