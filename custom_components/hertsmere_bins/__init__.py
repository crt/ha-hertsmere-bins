"""The Hertsmere Bin Collection integration."""
from __future__ import annotations
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import PLATFORMS
from .coordinator import HertsmereBinsCoordinator

_LOGGER = logging.getLogger(__name__)

type HertsmereConfigEntry = ConfigEntry[HertsmereBinsCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: HertsmereConfigEntry) -> bool:
    """Set up Hertsmere Bin Collection from a config entry."""
    coordinator = HertsmereBinsCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: HertsmereConfigEntry
) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: HertsmereConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
