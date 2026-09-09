"""Constants for the Hertsmere Bin Collection integration."""
from __future__ import annotations
DOMAIN = "hertsmere_bins"
PLATFORMS = ["sensor", "binary_sensor"]
STORAGE_VERSION = 1
DEFAULT_UPDATE_HOURS = 3

CONF_BASE_URL = "base_url"
CONF_VERSION = "version"
CONF_COLLECTION_DAY = "collection_day"
CONF_THRESHOLD_DAYS = "threshold_days"
CONF_NAME_FOOD = "name_food"
CONF_NAME_REFUSE = "name_refuse"
CONF_NAME_RECYCLING = "name_recycling"
CONF_NAME_GARDEN = "name_garden"
CONF_BH_NOTE = "bank_holiday_note"
CONF_EXPIRY_NOTE = "expiry_note"
CONF_TITLE_PREFIX = "title_prefix"
CONF_UPDATE_HOURS = "update_hours"
CONF_UPCOMING_DAYS = "upcoming_days"

DEFAULT_THRESHOLD_DAYS = 21
DEFAULT_UPCOMING_DAYS = 1
DEFAULT_VERSION = "B"
DEFAULT_DAY = "Monday"
