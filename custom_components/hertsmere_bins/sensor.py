"""Sensor showing the current week's bin collection."""
from __future__ import annotations
from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import HertsmereBinsCoordinator
from .entity import device_info

if TYPE_CHECKING:
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
    from . import HertsmereConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: "HertsmereConfigEntry",
    async_add_entities: "AddConfigEntryEntitiesCallback",
) -> None:
    async_add_entities([HertsmereBinsSensor(entry.runtime_data, entry)])


class HertsmereBinsSensor(CoordinatorEntity[HertsmereBinsCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:trash-can-outline"
    _attr_translation_key = "this_week"

    def __init__(self, coordinator: HertsmereBinsCoordinator, entry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_this_week"
        self._attr_device_info = device_info(entry)

    @property
    def native_value(self) -> str:
        return self.coordinator.data.summary

    @property
    def extra_state_attributes(self) -> dict:
        d = self.coordinator.data
        return {
            "week": d.week,
            "collection_day": d.collection_day,
            "collection_date": d.collection_date,
            "bins": d.bins,
            "is_collection_day": d.is_collection_day,
            "upcoming": d.upcoming,
            "bank_holiday_week": d.bank_holiday_week,
            "bank_holidays": d.bank_holidays,
            "bank_holiday_note": d.bank_holiday_note,
            "expiring_soon": d.expiring_soon,
            "expiry_note": d.expiry_note,
            "days_until_expiry": d.days_until_expiry,
            "valid_until": d.valid_until,
            "title_prefix": d.title_prefix,
            "source": d.source,
            "download_error": d.download_error,
        }
