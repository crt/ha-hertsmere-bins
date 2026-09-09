"""Config and options flow for Hertsmere Bin Collection."""
from __future__ import annotations
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import (
    ConfigFlow, ConfigFlowResult, OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector, NumberSelectorConfig, NumberSelectorMode,
    SelectSelector, SelectSelectorConfig, SelectSelectorMode, TextSelector,
)
import homeassistant.util.dt as dt_util

from . import core
from .const import (
    CONF_BASE_URL, CONF_BH_NOTE, CONF_COLLECTION_DAY, CONF_EXPIRY_NOTE,
    CONF_NAME_FOOD, CONF_NAME_GARDEN, CONF_NAME_RECYCLING, CONF_NAME_REFUSE,
    CONF_THRESHOLD_DAYS, CONF_TITLE_PREFIX, CONF_UPDATE_HOURS, CONF_UPCOMING_DAYS,
    CONF_VERSION, DEFAULT_DAY, DEFAULT_THRESHOLD_DAYS, DEFAULT_UPDATE_HOURS,
    DEFAULT_UPCOMING_DAYS, DEFAULT_VERSION, DOMAIN,
)

DAY_SELECTOR = SelectSelector(SelectSelectorConfig(
    options=core.WEEKDAYS, mode=SelectSelectorMode.DROPDOWN))
VERSION_SELECTOR = SelectSelector(SelectSelectorConfig(
    options=["A", "B"], mode=SelectSelectorMode.LIST))


async def _validate(hass: HomeAssistant, data: dict[str, Any]) -> str | None:
    """Download+parse the current period; return an error key or None."""
    ref = dt_util.now().date()
    year, half = core.period_containing(ref)
    url = core.build_url(data[CONF_BASE_URL], year, half, data[CONF_VERSION])
    session = async_get_clientsession(hass)
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
            resp.raise_for_status()
            raw = await resp.read()
    except (aiohttp.ClientError, TimeoutError):
        return "cannot_connect"
    try:
        labels = await hass.async_add_executor_job(core.parse_pdf_bytes, raw)
    except Exception:  # noqa: BLE001
        return "parse_error"
    return None if labels else "empty"


def _base_schema(cur: dict[str, Any]) -> vol.Schema:
    return vol.Schema({
        vol.Required(CONF_COLLECTION_DAY,
                     default=cur.get(CONF_COLLECTION_DAY, DEFAULT_DAY)): DAY_SELECTOR,
        vol.Required(CONF_VERSION,
                     default=cur.get(CONF_VERSION, DEFAULT_VERSION)): VERSION_SELECTOR,
        vol.Required(CONF_BASE_URL,
                     default=cur.get(CONF_BASE_URL, core.DEFAULT_BASE_URL)): TextSelector(),
    })


class HertsmereBinsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial UI setup."""
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if err := await _validate(self.hass, user_input):
                errors["base"] = err
            else:
                await self.async_set_unique_id(
                    f"{user_input[CONF_BASE_URL]}|{user_input[CONF_VERSION]}"
                    f"|{user_input[CONF_COLLECTION_DAY]}"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=(f"Hertsmere bins "
                           f"({user_input[CONF_COLLECTION_DAY]}, "
                           f"{user_input[CONF_VERSION]})"),
                    data=user_input,
                )
        return self.async_show_form(
            step_id="user", data_schema=_base_schema(user_input or {}), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> "HertsmereBinsOptionsFlow":
        return HertsmereBinsOptionsFlow()


class HertsmereBinsOptionsFlow(OptionsFlow):
    """Edit day, version, URL, expiry threshold and bin display names."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        cur = {**self.config_entry.data, **self.config_entry.options}
        schema = vol.Schema({
            vol.Required(CONF_COLLECTION_DAY,
                         default=cur.get(CONF_COLLECTION_DAY, DEFAULT_DAY)): DAY_SELECTOR,
            vol.Required(CONF_VERSION,
                         default=cur.get(CONF_VERSION, DEFAULT_VERSION)): VERSION_SELECTOR,
            vol.Required(CONF_BASE_URL,
                         default=cur.get(CONF_BASE_URL, core.DEFAULT_BASE_URL)): TextSelector(),
            vol.Required(CONF_THRESHOLD_DAYS,
                         default=cur.get(CONF_THRESHOLD_DAYS, DEFAULT_THRESHOLD_DAYS)):
                NumberSelector(NumberSelectorConfig(
                    min=1, max=120, mode=NumberSelectorMode.BOX,
                    unit_of_measurement="days")),
            vol.Required(CONF_UPCOMING_DAYS,
                         default=cur.get(CONF_UPCOMING_DAYS, DEFAULT_UPCOMING_DAYS)):
                NumberSelector(NumberSelectorConfig(
                    min=0, max=14, step=1, mode=NumberSelectorMode.BOX,
                    unit_of_measurement="days")),
            vol.Required(CONF_UPDATE_HOURS,
                         default=cur.get(CONF_UPDATE_HOURS, DEFAULT_UPDATE_HOURS)):
                NumberSelector(NumberSelectorConfig(
                    min=1, max=48, step=1, mode=NumberSelectorMode.BOX,
                    unit_of_measurement="hours")),
            vol.Optional(CONF_NAME_FOOD,
                         default=cur.get(CONF_NAME_FOOD, core.DEFAULT_BIN_NAMES["food"])): TextSelector(),
            vol.Optional(CONF_NAME_REFUSE,
                         default=cur.get(CONF_NAME_REFUSE, core.DEFAULT_BIN_NAMES["refuse"])): TextSelector(),
            vol.Optional(CONF_NAME_RECYCLING,
                         default=cur.get(CONF_NAME_RECYCLING, core.DEFAULT_BIN_NAMES["recycling"])): TextSelector(),
            vol.Optional(CONF_NAME_GARDEN,
                         default=cur.get(CONF_NAME_GARDEN, core.DEFAULT_BIN_NAMES["garden"])): TextSelector(),
            vol.Optional(CONF_BH_NOTE,
                         default=cur.get(CONF_BH_NOTE, core.DEFAULT_BH_NOTE)): TextSelector(),
            vol.Optional(CONF_EXPIRY_NOTE,
                         default=cur.get(CONF_EXPIRY_NOTE, core.DEFAULT_EXPIRY_NOTE)): TextSelector(),
            vol.Optional(CONF_TITLE_PREFIX,
                         default=cur.get(CONF_TITLE_PREFIX, core.DEFAULT_TITLE_PREFIX)): TextSelector(),
        })
        return self.async_show_form(step_id="init", data_schema=schema)
