import json
from pathlib import Path

from src.data_cleaning import clean_articles, normalize_title


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_assignment_articles():
    path = PROJECT_ROOT / "data" / "raw" / "articles.json"

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def test_assignment_dataset_has_five_input_records():
    records = load_assignment_articles()

    assert len(records) == 5


def test_assignment_dataset_removes_one_duplicate():
    cleaned, report = clean_articles(load_assignment_articles())

    assert report["input_count"] == 5
    assert report["duplicates_removed"] == 1
    assert report["output_count"] == 4


def test_ambiguous_date_is_reported_before_duplicate_removal():
    cleaned, report = clean_articles(load_assignment_articles())

    assert report["ambiguous_dates_flagged"] == 1
    assert report["ambiguous_date_details"][0]["raw_date"] == "08/01/2026"


def test_duplicate_keeps_first_valid_record():
    cleaned, report = clean_articles(load_assignment_articles())

    article = next(
        row for row in cleaned
        if row["title"] == "City Council Approves New Transit Line"
    )

    assert article["topic"] == "local"
    assert article["date"] == "2026-08-01"


def test_topics_are_normalized_to_lowercase():
    cleaned, _ = clean_articles(load_assignment_articles())

    assert all(row["topic"] == row["topic"].lower() for row in cleaned)


def test_invalid_article_is_skipped_and_counted():
    records = [
        {
            "title": "Valid Article",
            "topic": "business",
            "date": "2026-08-03"
        },
        {
            "title": "Invalid Article",
            "topic": "local",
            "date": "not-a-date"
        }
    ]

    cleaned, report = clean_articles(records)

    assert len(cleaned) == 1
    assert report["invalid_count"] == 1


def test_extra_title_whitespace_is_normalized():
    assert normalize_title(
        "  City   Council Approves New Transit Line  "
    ) == "City Council Approves New Transit Line"


def test_deduplication_is_case_insensitive():
    records = [
        {
            "title": "City Council News",
            "topic": "local",
            "date": "2026-08-01"
        },
        {
            "title": " city council news ",
            "topic": "LOCAL",
            "date": "2026-08-02"
        }
    ]

    cleaned, report = clean_articles(records)

    assert len(cleaned) == 1
    assert report["duplicates_removed"] == 1


def test_original_input_is_not_modified():
    records = load_assignment_articles()
    original = json.loads(json.dumps(records))

    clean_articles(records)

    assert records == original
