import pytest

from src.date_utils import (
    is_ambiguous_date,
    parse_publication_date,
)


def test_standard_iso_date():
    result = parse_publication_date("2026-08-01")

    assert result.parsed_date.isoformat() == "2026-08-01"
    assert result.ambiguous is False


def test_ambiguous_us_date_is_explicitly_flagged():
    result = parse_publication_date("08/01/2026")

    assert result.parsed_date.isoformat() == "2026-08-01"
    assert result.ambiguous is True
    assert result.source_format == "MM/DD/YYYY"


def test_unambiguous_day_month_date():
    result = parse_publication_date("13/04/2026")

    assert result.parsed_date.isoformat() == "2026-04-13"
    assert result.ambiguous is False


def test_same_day_and_month_is_not_ambiguous():
    result = parse_publication_date("05/05/2026")

    assert result.parsed_date.isoformat() == "2026-05-05"
    assert result.ambiguous is False


@pytest.mark.parametrize(
    "raw_date, expected",
    [
        ("2026-0803", "2026-08-03"),
        ("202608-06", "2026-08-06"),
    ]
)
def test_malformed_source_formats(raw_date, expected):
    result = parse_publication_date(raw_date)

    assert result.parsed_date.isoformat() == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        ("08/01/2026", True),
        ("03/04/2026", True),
        ("13/04/2026", False),
        ("05/05/2026", False),
        ("2026-08-01", False),
    ]
)
def test_ambiguity_detection(value, expected):
    assert is_ambiguous_date(value) is expected


def test_invalid_date_raises_error():
    with pytest.raises(ValueError):
        parse_publication_date("2026-02-30")


def test_unknown_format_raises_error():
    with pytest.raises(ValueError):
        parse_publication_date("August 1st 2026")
