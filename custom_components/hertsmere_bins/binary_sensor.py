"""Binary sensors: calendar expiring soon, and bank-holiday week."""
from __future__ import annotations
from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass, BinarySensorEntity,
)
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
    coordinator = entry.runtime_data
    async_add_entities([
        HertsmereExpiringSoon(coordinator, entry),
        HertsmereBankHolidayWeek(coordinator, entry),
    ])


class _Base(CoordinatorEntity[HertsmereBinsCoordinator], BinarySensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: HertsmereBinsCoordinator, entry, suffix: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{suffix}"
        self._attr_device_info = device_info(entry)


class HertsmereExpiringSoon(_Base):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "expiring_soon"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "expiring_soon")

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.expiring_soon

    @property
    def extra_state_attributes(self) -> dict:
        d = self.coordinator.data
        return {
            "valid_until": d.valid_until,
            "days_until_expiry": d.days_until_expiry,
            "download_error": d.download_error,
        }


class HertsmereBankHolidayWeek(_Base):
    _attr_icon = "mdi:calendar-alert"
    _attr_translation_key = "bank_holiday_week"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "bank_holiday_week")

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.bank_holiday_week

    @property
    def extra_state_attributes(self) -> dict:
        return {"bank_holidays": self.coordinator.data.bank_holidays}
