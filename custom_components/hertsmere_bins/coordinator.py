"""DataUpdateCoordinator: download, parse, cache and refresh the calendar."""
from __future__ import annotations
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

import aiohttp
from homeassistant.components import persistent_notification
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.loader import async_get_integration
import homeassistant.util.dt as dt_util

from . import core
from .const import (
    CONF_BASE_URL, CONF_BH_NOTE, CONF_COLLECTION_DAY, CONF_EXPIRY_NOTE,
    CONF_NAME_FOOD, CONF_NAME_GARDEN, CONF_NAME_RECYCLING, CONF_NAME_REFUSE,
    CONF_THRESHOLD_DAYS, CONF_TITLE_PREFIX, CONF_UPDATE_HOURS, CONF_UPCOMING_DAYS,
    CONF_VERSION, DEFAULT_DAY, DEFAULT_THRESHOLD_DAYS, DEFAULT_UPDATE_HOURS,
    DEFAULT_UPCOMING_DAYS, DEFAULT_VERSION, DOMAIN, STORAGE_VERSION,
)

if TYPE_CHECKING:
    from . import HertsmereConfigEntry

_LOGGER = logging.getLogger(__name__)


@dataclass
class BinsData:
    """Everything the entities need for one update."""
    week: str
    collection_day: str
    collection_date: str
    bins: list[str]
    summary: str
    bank_holiday_week: bool
    bank_holidays: list[dict]
    is_collection_day: bool
    bank_holiday_note: str
    expiry_note: str
    title_prefix: str
    valid_until: str | None
    days_until_expiry: int | None
    expiring_soon: bool
    upcoming: bool
    source: str | None
    download_error: str | None


class HertsmereBinsCoordinator(DataUpdateCoordinator[BinsData]):
    """Fetch the PDF only when needed; compute the current week every update."""

    config_entry: "HertsmereConfigEntry"

    def __init__(self, hass: HomeAssistant, entry: "HertsmereConfigEntry") -> None:
        opts = {**entry.data, **entry.options}
        try:
            hours = float(opts.get(CONF_UPDATE_HOURS, DEFAULT_UPDATE_HOURS))
        except (TypeError, ValueError):
            hours = DEFAULT_UPDATE_HOURS
        if hours <= 0:
            hours = DEFAULT_UPDATE_HOURS
        super().__init__(
            hass, _LOGGER, name=DOMAIN,
            update_interval=timedelta(hours=hours), config_entry=entry,
        )
        self._store: Store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self._labels: dict[str, str] = {}
        self._sources: set[str] = set()
        self._loaded = False
        self._integration_version: str | None = None

    def _opts(self) -> dict[str, Any]:
        return {**self.config_entry.data, **self.config_entry.options}

    async def _async_load_cache(self) -> None:
        if self._loaded:
            return
        integration = await async_get_integration(self.hass, DOMAIN)
        current_version = integration.version
        cached = await self._store.async_load()
        if cached:
            if cached.get("integration_version") != str(current_version):
                _LOGGER.debug(
                    "hertsmere_bins updated (%s -> %s); discarding cached calendar "
                    "so it is re-downloaded and re-parsed",
                    cached.get("integration_version"), current_version,
                )
            else:
                self._labels = dict(cached.get("labels", {}))
                self._sources = set(cached.get("sources", []))
        self._loaded = True
        self._integration_version = str(current_version)

    async def _async_save_cache(self) -> None:
        await self._store.async_save({
            "labels": self._labels,
            "sources": sorted(self._sources),
            "integration_version": self._integration_version,
        })

    async def _ensure_period(self, year: int, half: str, opts: dict) -> str | None:
        """Ingest a period's PDF if not already stored. Returns error string or None."""
        base = opts.get(CONF_BASE_URL) or core.DEFAULT_BASE_URL
        version = opts.get(CONF_VERSION, DEFAULT_VERSION)
        fname = core.build_filename(year, half, version)
        if fname in self._sources:
            return None
        url = core.build_url(base, year, half, version)
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                resp.raise_for_status()
                raw = await resp.read()
        except (aiohttp.ClientError, TimeoutError) as err:
            return f"download failed for {url}: {err}"
        try:
            labels = await self.hass.async_add_executor_job(core.parse_pdf_bytes, raw)
        except Exception as err:  # noqa: BLE001 - pypdf raises many types
            return f"parse failed for {fname}: {err}"
        if not labels:
            return f"no dated cells parsed from {fname}"
        self._labels.update(labels)
        self._sources.add(fname)
        await self._async_save_cache()
        return None

    async def _async_update_data(self) -> BinsData:
        await self._async_load_cache()
        opts = self._opts()
        day = opts.get(CONF_COLLECTION_DAY, DEFAULT_DAY)
        threshold = int(opts.get(CONF_THRESHOLD_DAYS, DEFAULT_THRESHOLD_DAYS))
        upcoming_days = int(opts.get(CONF_UPCOMING_DAYS, DEFAULT_UPCOMING_DAYS))
        names = {
            "food": opts.get(CONF_NAME_FOOD) or core.DEFAULT_BIN_NAMES["food"],
            "refuse": opts.get(CONF_NAME_REFUSE) or core.DEFAULT_BIN_NAMES["refuse"],
            "recycling": opts.get(CONF_NAME_RECYCLING) or core.DEFAULT_BIN_NAMES["recycling"],
            "garden": opts.get(CONF_NAME_GARDEN) or core.DEFAULT_BIN_NAMES["garden"],
        }
        bh_note = opts.get(CONF_BH_NOTE, core.DEFAULT_BH_NOTE)
        expiry_note = opts.get(CONF_EXPIRY_NOTE, core.DEFAULT_EXPIRY_NOTE)
        title_prefix = opts.get(CONF_TITLE_PREFIX, core.DEFAULT_TITLE_PREFIX)
        ref = dt_util.now().date()
        download_error: str | None = None

        year, half = core.period_containing(ref)
        if err := await self._ensure_period(year, half, opts):
            download_error = err
            if not self._labels:
                raise UpdateFailed(err)

        _, _, soon = core.expiry_info(self._labels, ref, threshold)
        if soon:
            ny, nh = core.next_period(year, half)
            if nerr := await self._ensure_period(ny, nh, opts):
                download_error = nerr
                persistent_notification.async_create(
                    self.hass,
                    "Could not download the upcoming Hertsmere calendar "
                    f"({core.build_filename(ny, nh, opts.get(CONF_VERSION, DEFAULT_VERSION))}). "
                    f"Current data expires soon.\n\n{nerr}",
                    title="Hertsmere bins: calendar update needed",
                    notification_id=f"{DOMAIN}_download",
                )
            else:
                persistent_notification.async_dismiss(self.hass, f"{DOMAIN}_download")

        state = await self.hass.async_add_executor_job(
            core.current_week, self._labels, day, ref, names
        )
        if state is None:
            raise UpdateFailed("current date is outside the parsed calendar range")
        valid_until, days_left, expiring_soon = core.expiry_info(self._labels, ref, threshold)
        diff = (date.fromisoformat(state["collection_date"]) - ref).days
        upcoming = 0 <= diff <= upcoming_days
        return BinsData(
            **state, bank_holiday_note=bh_note, expiry_note=expiry_note,
            title_prefix=title_prefix, valid_until=valid_until,
            days_until_expiry=days_left, expiring_soon=expiring_soon,
            upcoming=upcoming,
            source=", ".join(sorted(self._sources)) or None,
            download_error=download_error,
        )
