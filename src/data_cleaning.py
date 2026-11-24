"""Validate, normalize, and deduplicate news article records."""

import json
from pathlib import Path

from src.date_utils import parse_publication_date


def normalize_title(title: str) -> str:
    """Remove extra whitespace while preserving the original capitalization."""
    return " ".join(title.split())


def clean_articles(records: list[dict]) -> tuple[list[dict], dict]:
    """
    Clean article records.

    Decisions:
    - Normalize whitespace in titles.
    - Compare duplicate titles without considering capitalization.
    - Convert topics to lowercase.
    - Normalize supported publication date formats.
    - Keep the first valid occurrence of a duplicate title.
    - Report ambiguous dates before duplicate removal.
    - Skip invalid records and report their count.
    """
    cleaned_records = []
    seen_titles = set()

    invalid_count = 0
    duplicates_removed = 0
    ambiguous_date_details = []

    for index, record in enumerate(records):

        try:
            if not isinstance(record, dict):
                raise ValueError("Article record must be a JSON object.")

            title = record.get("title")
            topic = record.get("topic")
            raw_date = record.get("date")

            if not all(
                isinstance(value, str)
                for value in (title, topic, raw_date)
            ):
                raise ValueError(
                    "title, topic, and date must all be strings."
                )

            title = normalize_title(title)
            topic = topic.strip().lower()

            if not title:
                raise ValueError("Article title cannot be empty.")

            if not topic:
                raise ValueError("Article topic cannot be empty.")

            date_result = parse_publication_date(raw_date)

            # Count ambiguity before deduplication. Otherwise the duplicate
            # record containing the ambiguous date would disappear.
            if date_result.ambiguous:
                ambiguous_date_details.append({
                    "record_index": index,
                    "raw_date": raw_date,
                    "interpreted_date": date_result.parsed_date.isoformat(),
                    "selected_format": date_result.source_format,
                    "reason": date_result.interpretation
                })

            # Title is used because the assignment does not supply article IDs.
            title_key = title.casefold()

            if title_key in seen_titles:
                duplicates_removed += 1
                continue

            seen_titles.add(title_key)

            cleaned_records.append({
                "title": title,
                "topic": topic,
                "date": date_result.parsed_date.isoformat()
            })

        except (ValueError, TypeError, AttributeError) as error:
            invalid_count += 1

            print(
                f"Skipping invalid record at index {index}: {error}"
            )

    report = {
        "input_count": len(records),
        "invalid_count": invalid_count,
        "duplicates_removed": duplicates_removed,
        "ambiguous_dates_flagged": len(ambiguous_date_details),
        "ambiguous_date_details": ambiguous_date_details,
        "output_count": len(cleaned_records)
    }

    return cleaned_records, report


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]

    input_path = project_root / "data" / "raw" / "articles.json"
    output_dir = project_root / "data" / "processed"

    cleaned_output = output_dir / "cleaned_articles.json"
    report_output = output_dir / "cleaning_report.json"

    with input_path.open("r", encoding="utf-8") as file:
        raw_records = json.load(file)

    if not isinstance(raw_records, list):
        raise ValueError("The article input must contain a JSON list.")

    cleaned_records, report = clean_articles(raw_records)

    output_dir.mkdir(parents=True, exist_ok=True)

    with cleaned_output.open("w", encoding="utf-8") as file:
        json.dump(
            cleaned_records,
            file,
            indent=2,
            ensure_ascii=False
        )
        file.write("\n")

    with report_output.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2)
        file.write("\n")

    print("\n===== ARTICLE CLEANING REPORT =====")

    for key, value in report.items():
        print(f"{key}: {value}")

    print(f"\nCleaned articles: {cleaned_output}")
    print(f"Cleaning report: {report_output}")


if __name__ == "__main__":
    main()
