"""Pure logic for the Hertsmere bins integration: URL/period math, PDF parsing,
current-week, bank-holiday and expiry computation. No Home Assistant imports."""
from __future__ import annotations
import io, re
from datetime import date, timedelta

DEFAULT_BASE_URL = ("https://www.hertsmere.gov.uk/asset-library/Documents/"
                    "04-Environment-Refuse-Recycling/Recycling-Waste/")
FILENAME_TEMPLATE = "Waste-collection-calendar-{year}-{half}-{version}.pdf"

WEEKDAYS = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
WEEK_BINS = {"W1": ["food", "refuse"], "W2": ["food", "recycling", "garden"]}
DEFAULT_BIN_NAMES = {"food": "Food waste (silver bin)",
                     "refuse": "Non-recyclable (black bin)",
                     "recycling": "Mixed recycling (brown bin)",
                     "garden": "Garden waste (green bin)"}
DEFAULT_BH_NOTE = "\u26a0 Bank holiday this week - collection may be delayed"
DEFAULT_EXPIRY_NOTE = "Calendar expires soon - a new one will be fetched automatically"
DEFAULT_TITLE_PREFIX = "Bin collection:"
HOLIDAY_SUBDIV = "England"

_MONTHS = {m: i for i, m in enumerate(
    ["January","February","March","April","May","June",
     "July","August","September","October","November","December"], start=1)}
_HEADER_RE = re.compile(r"\b(" + "|".join(_MONTHS) + r")\s+(\d{4})")
_HEADER_LINE_RE = re.compile(r"^\s*(" + "|".join(_MONTHS) + r")\s+(\d{4})\s*$")
_WLINE_RE = re.compile(r"(W[12])((?:\s+\d{1,2})+)")


# ---- period / URL ----------------------------------------------------------
def half_for(d: date) -> str:
    return "jan-jun" if d.month <= 6 else "jul-dec"

def period_containing(d: date) -> tuple[int, str]:
    return d.year, half_for(d)

def next_period(year: int, half: str) -> tuple[int, str]:
    return (year, "jul-dec") if half == "jan-jun" else (year + 1, "jan-jun")

def build_filename(year, half, version, template=FILENAME_TEMPLATE) -> str:
    return template.format(year=year, half=half, version=str(version).upper())

def build_url(base_url, year, half, version, template=FILENAME_TEMPLATE) -> str:
    if not base_url.endswith("/"):
        base_url += "/"
    return base_url + build_filename(year, half, version, template)


# ---- PDF -> single-column lines via coordinate reflow (robust to layout) ----
def _fragments(pdf_bytes: bytes):
    """Collect (page, x, y, text) fragments from every text-showing operator."""
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(pdf_bytes))
    frags: list[tuple[int, float, float, str]] = []

    def visitor(page_no):
        def v(text, cm, tm, font_dict, font_size):
            if text and text.strip():
                frags.append((page_no, round(tm[4], 1), round(tm[5], 1), text))
        return v

    for pno, page in enumerate(reader.pages):
        page.extract_text(visitor_text=visitor(pno))
    return frags


def _column_boundaries(frags):
    """Cluster the x-positions of month headers into columns; return split xs."""
    xs = sorted(x for (_, x, _, t) in frags if _HEADER_RE.search(t))
    anchors: list[float] = []
    for x in xs:
        if not anchors or x - anchors[-1] > 40:   # new column if >40pt gap
            anchors.append(x)
    return [(anchors[i] + anchors[i + 1]) / 2 for i in range(len(anchors) - 1)]


def reflow_single_column(pdf_bytes: bytes) -> list[str]:
    """Reflow a possibly multi-column PDF into one column: each column read
    top-to-bottom, columns left-to-right. Returns a list of text lines."""
    frags = _fragments(pdf_bytes)
    if not frags:
        return []
    bounds = _column_boundaries(frags)

    def col_of(x):
        return sum(1 for b in bounds if x >= b)

    lines: list[str] = []
    for col in range(len(bounds) + 1):
        col_frags = [f for f in frags if col_of(f[1]) == col]
        # group into visual rows by (page, y) with a small tolerance
        col_frags.sort(key=lambda f: (f[0], -f[2], f[1]))
        row, last = [], None
        for (p, x, y, t) in col_frags:
            if last is not None and (p != last[0] or abs(y - last[1]) > 3):
                lines.append(" ".join(s for _, s in sorted(row)))
                row = []
            row.append((x, t))
            last = (p, y)
        if row:
            lines.append(" ".join(s for _, s in sorted(row)))
    return lines


def parse_lines(lines) -> dict[str, str]:
    """Parse single-column lines into {ISO-date: 'W1'|'W2'}."""
    labels: dict[str, str] = {}
    month = year = None
    for line in lines:
        m = _HEADER_LINE_RE.match(line) or _HEADER_RE.search(line)
        if m and (_HEADER_LINE_RE.match(line) or not _WLINE_RE.search(line)):
            month, year = _MONTHS[m.group(1)], int(m.group(2))
            continue
        if month is None:
            continue
        for wm in _WLINE_RE.finditer(line):
            label = wm.group(1)
            for d in re.findall(r"\d{1,2}", wm.group(2)):
                if 1 <= int(d) <= 31:
                    try:
                        labels[date(year, month, int(d)).isoformat()] = label
                    except ValueError:
                        pass
    return labels


# ---- fallback: band parser on -layout text (kept for safety) ---------------
def _bands(headers):
    out = []
    for i, (col, mo, yr) in enumerate(headers):
        left = 0 if i == 0 else (headers[i - 1][0] + col) // 2
        right = (col + headers[i + 1][0]) // 2 if i + 1 < len(headers) else 10**9
        out.append((left, right, mo, yr))
    return out

def parse_layout_text(text: str) -> dict[str, str]:
    labels, bands = {}, []
    for line in text.splitlines():
        headers = sorted((m.start(), _MONTHS[m.group(1)], int(m.group(2)))
                         for m in _HEADER_RE.finditer(line))
        if headers:
            bands = _bands(headers)
            continue
        if not bands:
            continue
        for left, right, mo, yr in bands:
            for wm in _WLINE_RE.finditer(line[left:right]):
                label = wm.group(1)
                for d in re.findall(r"\d{1,2}", wm.group(2)):
                    if 1 <= int(d) <= 31:
                        try:
                            labels[date(yr, mo, int(d)).isoformat()] = label
                        except ValueError:
                            pass
    return labels


def parse_pdf_bytes(pdf_bytes: bytes) -> dict[str, str]:
    """Primary: coordinate reflow -> single-column parse. Fallback: band parser."""
    labels = parse_lines(reflow_single_column(pdf_bytes))
    if labels:
        return labels
    from pypdf import PdfReader
    text = "\n".join((p.extract_text(extraction_mode="layout") or "")
                     for p in PdfReader(io.BytesIO(pdf_bytes)).pages)
    return parse_layout_text(text)


# ---- bank holidays ---------------------------------------------------------
_HOLIDAY_CACHE: dict = {}


def _uk_holiday_map(years: tuple, subdiv: str) -> dict:
    """Return {date: name} for the given years, cached. Imports `holidays`
    lazily; callers must invoke this off the event loop (it does file I/O)."""
    key = (years, subdiv)
    cached = _HOLIDAY_CACHE.get(key)
    if cached is None:
        import holidays
        cached = dict(holidays.UnitedKingdom(subdiv=subdiv, years=years))
        _HOLIDAY_CACHE[key] = cached
    return cached


def bank_holidays_in_week(ref: date, subdiv: str = HOLIDAY_SUBDIV):
    """Return [{'date':iso,'name':str}] for bank holidays in ref's Mon-Sun week."""
    monday = ref - timedelta(days=ref.weekday())
    years = tuple(sorted({monday.year, (monday + timedelta(days=6)).year}))
    try:
        cal = _uk_holiday_map(years, subdiv)
    except ImportError:
        return []
    out = []
    for i in range(7):
        d = monday + timedelta(days=i)
        if d in cal:
            out.append({"date": d.isoformat(), "name": cal[d]})
    return out


# ---- current week + expiry -------------------------------------------------
def current_week(labels, day, ref, names=None, subdiv=HOLIDAY_SUBDIV):
    names = {**DEFAULT_BIN_NAMES, **(names or {})}
    monday = ref - timedelta(days=ref.weekday())
    coll = monday + timedelta(days=WEEKDAYS.index(day))
    label = labels.get(coll.isoformat()) or next(
        (labels[(monday + timedelta(days=i)).isoformat()]
         for i in range(7) if (monday + timedelta(days=i)).isoformat() in labels), None)
    if label is None:
        return None
    bins = [names[k] for k in WEEK_BINS[label]]
    bh = bank_holidays_in_week(ref, subdiv)
    return {"week": label,
            "collection_day": day, "collection_date": coll.isoformat(),
            "bins": bins, "summary": f"{day}: " + ", ".join(bins),
            "bank_holiday_week": bool(bh), "bank_holidays": bh,
            "is_collection_day": coll == ref}


def expiry_info(labels, ref, threshold_days):
    if not labels:
        return None, None, True
    end = max(date.fromisoformat(k) for k in labels)
    days = (end - ref).days
    return end.isoformat(), days, days <= threshold_days
