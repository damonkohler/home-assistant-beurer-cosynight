"""Shared helpers for Beurer CosyNight integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo

from . import beurer_cosynight
from .const import DOMAIN


def device_info_for(device: beurer_cosynight.Device) -> DeviceInfo:
    """Return consistent DeviceInfo for a CosyNight device."""
    return DeviceInfo(
        identifiers={(DOMAIN, device.id)},
        name=device.name,
        manufacturer="Beurer",
        model="CosyNight",
    )
