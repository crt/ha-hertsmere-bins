# Hertsmere Bin Collection (Home Assistant custom integration)

Downloads the Hertsmere waste-collection calendar PDF, parses it, and exposes the
current week's bins as native entities. Config is entirely through the UI.

## Entities
- **sensor** `This week` - state is a summary (e.g. `Friday: Food waste, Non-recyclable`),
  with attributes: `week` (raw W1/W2 - internal label only),
  `collection_day`, `collection_date`, `bins`, `bank_holiday_week`, `bank_holidays`,
  `valid_until`, `days_until_expiry`, `expiring_soon`, `source`, `download_error`.
- **binary_sensor** `Calendar expiring soon` (device class *problem*).
- **binary_sensor** `Bank holiday week` - on when a bank holiday falls in the current
  collection week; use it to recolour your card. The summary also gets a short note
  appended (configurable).

## How it works
- URL = **base URL + version letter (A/B) + current half-year**, e.g.
  `...Waste-collection-calendar-2026-jul-dec-B.pdf`.
- The PDF is fetched **only when needed** (first run, or near expiry) and parsed into a
  date -> W1/W2 map cached in `.storage`; daily updates are pure date math.
- Parsing uses **coordinate-based single-column reflow**: text is extracted with its
  (x, y) positions and re-flowed so multi-column calendars are read one column at a
  time. This is layout-robust; a band-based parser on layout text is kept as a fallback.
- Within *threshold* days of expiry, the next half-year PDF is fetched automatically;
  on failure you get a persistent notification and `expiring_soon` turns on.
- **Bank holidays** come from the `holidays` library (England), computed offline.
- `pypdf` and `holidays` are declared in `manifest.json` requirements, so HA installs
  them - nothing to install by hand, and they survive updates.

## Install

### Via HACS
1. HACS -> the three-dot menu (top right) -> **Custom repositories** -> add
   `https://github.com/crt/ha-hertsmere-bins` as an **Integration**.
2. Find **Hertsmere Bin Collection** in HACS and install it, then restart HA.

### Manual
1. Copy `custom_components/hertsmere_bins/` into `config/custom_components/` and restart HA.

### Then
1. **Settings -> Devices & Services -> Add Integration -> Hertsmere Bin Collection.**
2. Pick your collection weekday and version letter; the base URL default is fine.

## Options (Configure)
Collection weekday, version, base URL, renewal threshold (days), display names for the
four bins (this is the actual text shown in the state and the `bins` attribute), and the
**bank-holiday note** text (blank to append nothing). W1 weeks show food + non-recyclable;
W2 weeks show food + recycling + garden.

## Known limitations
- **Collection weekday** is not in the PDF (address-specific), so you set it.
- **Bank-holiday day-shifts** are not modelled: the bank-holiday flag/note tell you the
  week may differ, but the exact shifted day isn't computed.
- **W1/W2 -> bin mapping** follows Hertsmere's current scheme (W1 = food + non-recyclable,
  W2 = food + recycling + garden). Edit `WEEK_BINS` in `core.py` if the council changes it.
- Parsing targets the current calendar layout; if a future layout breaks it, the setup
  step surfaces an error and the fallback parser is attempted.

## License
AGPL-3.0 - see [LICENSE](LICENSE).
