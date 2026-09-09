"""Shared device info for Hertsmere bins entities."""
from __future__ import annotations
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN


def device_info(entry: ConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Hertsmere bin collection",
        manufacturer="Hertsmere Borough Council",
        entry_type=None,
    )
