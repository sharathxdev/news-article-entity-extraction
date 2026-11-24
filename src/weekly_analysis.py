"""Calculate weekly article counts grouped by topic."""

import json
from collections import Counter
from pathlib import Path
from datetime import date


PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    PROJECT_ROOT / "data" / "processed" / "cleaned_articles.json"
)

OUTPUT_FILE = (
    PROJECT_ROOT / "data" / "processed" / "weekly_topic_counts.json"
)


def calculate_weekly_counts(articles):
    """Count articles by ISO calendar year, week, and topic."""

    counts = Counter()

    for article in articles:
        published_date = date.fromisoformat(article["date"])

        iso_week = published_date.isocalendar()

        topic = article["topic"].strip().lower()

        group = (iso_week.year, iso_week.week, topic)

        counts[group] += 1

    results = []

    for (year, week, topic), count in sorted(counts.items()):
        results.append({
            "year": year,
            "week_number": week,
            "week": f"{year}-W{week:02d}",
            "topic": topic,
            "article_count": count
        })

    return results


def main():
    with INPUT_FILE.open("r", encoding="utf-8") as file:
        articles = json.load(file)

    results = calculate_weekly_counts(articles)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(results, file, indent=2)
        file.write("\n")

    print("\n===== WEEKLY ARTICLE COUNTS =====")

    for row in results:
        print(
            f"{row['week']} | "
            f"{row['topic']} | "
            f"{row['article_count']} article(s)"
        )

    print(f"\nReport saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
