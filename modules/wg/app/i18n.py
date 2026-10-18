from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

I18N_DIR = Path(__file__).parent / "i18n"
SUPPORTED_LANGUAGES = ("de", "en")
DEFAULT_LANGUAGE = "de"


@lru_cache
def _catalog(language: str) -> dict[str, str]:
    path = I18N_DIR / f"{language}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def t(key: str, language: str = DEFAULT_LANGUAGE, **params: object) -> str:
    language = language if language in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
    text = _catalog(language).get(key, key)
    return text.format(**params) if params else text
