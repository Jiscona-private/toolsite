from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from babel.dates import format_date
from babel.numbers import format_currency

I18N_DIR = Path(__file__).parent / "i18n"
SUPPORTED_LANGUAGES = ("de", "en")
DEFAULT_LANGUAGE = "de"

# spec.md §9.1: de_DE / en_GB, not just "de"/"en" - that's what picks
# "28,80 €" vs "€28.80" and German vs. English weekday abbreviations.
_BABEL_LOCALE = {"de": "de_DE", "en": "en_GB"}

# spec.md §9.1: "Mo, 19.10." / "Mon 19 Oct" - a custom Babel pattern, not
# one of the named styles (short/medium/...).
_DAY_PATTERN = {"de": "EEE, d.M.", "en": "EEE d MMM"}

# design.md §2 Hero-Karte: "Sonntag, 25.10." - the full weekday name, not
# the abbreviated one _DAY_PATTERN uses.
_WEEKDAY_DATE_PATTERN = {"de": "EEEE, d.M.", "en": "EEEE, d MMM"}

MINUS_SIGN = "−"  # spec.md §9.1: real minus sign, not a hyphen


@lru_cache
def _catalog(language: str) -> dict[str, str]:
    path = I18N_DIR / f"{language}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def t(key: str, language: str = DEFAULT_LANGUAGE, **params: object) -> str:
    language = language if language in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
    text = _catalog(language).get(key, key)
    return text.format(**params) if params else text


def _locale(language: str) -> str:
    return _BABEL_LOCALE.get(language, _BABEL_LOCALE[DEFAULT_LANGUAGE])


def money(cents: int, language: str = DEFAULT_LANGUAGE) -> str:
    text = format_currency(Decimal(cents) / 100, "EUR", locale=_locale(language))
    return text.replace("-", MINUS_SIGN)


def day(value: date, language: str = DEFAULT_LANGUAGE) -> str:
    pattern = _DAY_PATTERN.get(language, _DAY_PATTERN[DEFAULT_LANGUAGE])
    text = format_date(value, format=pattern, locale=_locale(language))
    # Babel's de_DE weekday abbreviations carry a period ("Mo."); spec.md
    # §9.1's own example ("Mo, 19.10.") doesn't want it before the comma.
    return text.replace(".,", ",")


def weekday_date(value: date, language: str = DEFAULT_LANGUAGE) -> str:
    pattern = _WEEKDAY_DATE_PATTERN.get(language, _WEEKDAY_DATE_PATTERN[DEFAULT_LANGUAGE])
    return format_date(value, format=pattern, locale=_locale(language))


def week_label(value: date, language: str = DEFAULT_LANGUAGE) -> str:
    prefix = "KW" if language == "de" else "Week"
    return f"{prefix} {value.isocalendar()[1]}"


def week_range(start: date, language: str = DEFAULT_LANGUAGE) -> str:
    """e.g. "19.-25. Okt" (de) / "19-25 Oct" (en), per design.md §5.4."""
    end = start + timedelta(days=6)
    locale = _locale(language)
    end_month = format_date(end, format="MMM", locale=locale)
    if language == "de":
        if start.month == end.month:
            return f"{start.day}.–{end.day}. {end_month}"
        start_month = format_date(start, format="MMM", locale=locale)
        return f"{start.day}. {start_month} – {end.day}. {end_month}"
    if start.month == end.month:
        return f"{start.day}–{end.day} {end_month}"
    start_month = format_date(start, format="MMM", locale=locale)
    return f"{start.day} {start_month} – {end.day} {end_month}"
