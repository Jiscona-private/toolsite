import json

from app.i18n import I18N_DIR, SUPPORTED_LANGUAGES


def test_translation_files_have_the_same_keys() -> None:
    key_sets = {
        language: set(json.loads((I18N_DIR / f"{language}.json").read_text()))
        for language in SUPPORTED_LANGUAGES
    }
    de_keys, en_keys = key_sets["de"], key_sets["en"]
    assert de_keys == en_keys, f"Keys differ: {de_keys ^ en_keys}"
