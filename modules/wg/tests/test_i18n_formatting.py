from datetime import date

from app.i18n import MINUS_SIGN, day, money, week_label


def test_money_formats_positive_amount_de() -> None:
    assert money(2880, "de") == "28,80\xa0€"


def test_money_formats_positive_amount_en() -> None:
    assert money(2880, "en") == "€28.80"


def test_money_uses_real_minus_sign_for_negative_amounts() -> None:
    text = money(-2880, "de")
    assert MINUS_SIGN in text
    assert "-" not in text  # the plain ASCII hyphen-minus must be gone


def test_day_matches_spec_examples() -> None:
    # spec.md §9.1's own examples, for the Monday the rota starts on.
    assert day(date(2026, 10, 19), "de") == "Mo, 19.10."
    assert day(date(2026, 10, 19), "en") == "Mon 19 Oct"


def test_week_label_matches_spec_test_vector() -> None:
    # 2026-10-19 is KW 43 per spec.md §10.1's rotation table.
    assert week_label(date(2026, 10, 19), "de") == "KW 43"
    assert week_label(date(2026, 10, 19), "en") == "Week 43"
