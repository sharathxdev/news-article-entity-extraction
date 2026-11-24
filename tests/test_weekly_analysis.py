import json
from pathlib import Path

from src.weekly_analysis import calculate_weekly_counts


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_weekly_counts_match_assignment_results():
    input_file = (
        PROJECT_ROOT / "data" / "processed" / "cleaned_articles.json"
    )

    with input_file.open("r", encoding="utf-8") as file:
        articles = json.load(file)

    results = calculate_weekly_counts(articles)

    expected = [
        {
            "year": 2026,
            "week_number": 31,
            "week": "2026-W31",
            "topic": "local",
            "article_count": 1
        },
        {
            "year": 2026,
            "week_number": 32,
            "week": "2026-W32",
            "topic": "business",
            "article_count": 2
        },
        {
            "year": 2026,
            "week_number": 32,
            "week": "2026-W32",
            "topic": "sports",
            "article_count": 1
        }
    ]

    assert results == expected


def test_total_weekly_count_matches_number_of_articles():
    articles = [
        {"date": "2026-08-01", "topic": "local"},
        {"date": "2026-08-03", "topic": "business"},
        {"date": "2026-08-06", "topic": "sports"},
        {"date": "2026-08-09", "topic": "business"}
    ]

    results = calculate_weekly_counts(articles)

    total_count = sum(row["article_count"] for row in results)

    assert total_count == len(articles)


def test_iso_week_year_boundary():
    articles = [
        {"date": "2021-01-01", "topic": "local"},
        {"date": "2021-01-04", "topic": "local"}
    ]

    results = calculate_weekly_counts(articles)

    assert results == [
        {
            "year": 2020,
            "week_number": 53,
            "week": "2020-W53",
            "topic": "local",
            "article_count": 1
        },
        {
            "year": 2021,
            "week_number": 1,
            "week": "2021-W01",
            "topic": "local",
            "article_count": 1
        }
    ]


def test_topic_whitespace_and_capitalization():
    articles = [
        {"date": "2026-08-01", "topic": " BUSINESS "},
        {"date": "2026-08-02", "topic": "business"}
    ]

    results = calculate_weekly_counts(articles)

    assert len(results) == 1
    assert results[0]["topic"] == "business"
    assert results[0]["article_count"] == 2


def test_empty_article_list():
    assert calculate_weekly_counts([]) == []
