"""Date parsing utilities for news article publication dates."""

import re
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class DateParseResult:
    parsed_date: date
    source_format: str
    ambiguous: bool
    interpretation: str


def is_ambiguous_date(value: str) -> bool:
    """
    Detect slash dates that can represent two different valid dates.

    Example:
        08/01/2026 could mean August 1 or January 8.
    """
    if not isinstance(value, str):
        return False

    match = re.fullmatch(
        r"(\d{1,2})/(\d{1,2})/(\d{4})",
        value.strip()
    )

    if not match:
        return False

    first = int(match.group(1))
    second = int(match.group(2))

    return (
        1 <= first <= 12
        and 1 <= second <= 12
        and first != second
    )


def parse_publication_date(value: str) -> DateParseResult:
    """
    Parse the explicitly supported date formats.

    Supported:
        YYYY-MM-DD
        MM/DD/YYYY
        DD/MM/YYYY when the first number is greater than 12
        YYYY-MMDD (malformed source example)
        YYYYMM-DD (malformed source example)

    Ambiguous slash dates use the documented MM/DD/YYYY policy.
    The result records that ambiguity for the cleaning report.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Publication date must be a non-empty string.")

    value = value.strip()

    # Standard ISO format.
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        try:
            parsed = date.fromisoformat(value)
        except ValueError as error:
            raise ValueError(f"Invalid ISO publication date: {value}") from error

        return DateParseResult(
            parsed_date=parsed,
            source_format="YYYY-MM-DD",
            ambiguous=False,
            interpretation="Parsed as ISO date."
        )

    # Source example: 2026-0803 -> 2026-08-03.
    match = re.fullmatch(r"(\d{4})-(\d{2})(\d{2})", value)

    if match:
        year, month, day = map(int, match.groups())

        try:
            parsed = date(year, month, day)
        except ValueError as error:
            raise ValueError(f"Invalid compact date: {value}") from error

        return DateParseResult(
            parsed_date=parsed,
            source_format="YYYY-MMDD",
            ambiguous=False,
            interpretation="Normalized malformed YYYY-MMDD source format."
        )

    # Source example: 202608-06 -> 2026-08-06.
    match = re.fullmatch(r"(\d{4})(\d{2})-(\d{2})", value)

    if match:
        year, month, day = map(int, match.groups())

        try:
            parsed = date(year, month, day)
        except ValueError as error:
            raise ValueError(f"Invalid compact date: {value}") from error

        return DateParseResult(
            parsed_date=parsed,
            source_format="YYYYMM-DD",
            ambiguous=False,
            interpretation="Normalized malformed YYYYMM-DD source format."
        )

    # Slash-separated dates.
    match = re.fullmatch(
        r"(\d{1,2})/(\d{1,2})/(\d{4})",
        value
    )

    if match:
        first, second, year = map(int, match.groups())

        ambiguous = is_ambiguous_date(value)

        if first > 12 and second <= 12:
            # Example: 13/04/2026 can only be DD/MM/YYYY.
            day, month = first, second
            source_format = "DD/MM/YYYY"
            interpretation = "Interpreted as DD/MM/YYYY."

        elif second > 12 and first <= 12:
            # Example: 04/13/2026 can only be MM/DD/YYYY.
            month, day = first, second
            source_format = "MM/DD/YYYY"
            interpretation = "Interpreted as MM/DD/YYYY."

        else:
            # Ambiguous dates follow the documented US-date policy.
            month, day = first, second
            source_format = "MM/DD/YYYY"

            if ambiguous:
                interpretation = (
                    "Ambiguous slash date; interpreted as MM/DD/YYYY. "
                    "The assignment's duplicate ISO record supports "
                    "August 1 for 08/01/2026."
                )
            else:
                interpretation = (
                    "Both slash-date interpretations produce the same date."
                )

        try:
            parsed = date(year, month, day)
        except ValueError as error:
            raise ValueError(f"Invalid slash publication date: {value}") from error

        return DateParseResult(
            parsed_date=parsed,
            source_format=source_format,
            ambiguous=ambiguous,
            interpretation=interpretation
        )

    raise ValueError(f"Unsupported publication date format: {value}")


if __name__ == "__main__":
    examples = [
        "2026-08-01",
        "08/01/2026",
        "2026-0803",
        "202608-06",
        "13/04/2026"
    ]

    for example in examples:
        result = parse_publication_date(example)

        print(
            f"{example} -> {result.parsed_date.isoformat()} "
            f"| format={result.source_format} "
            f"| ambiguous={result.ambiguous}"
        )
