import json
from pathlib import Path

import pytest

from src.entity_evaluation import (
    calculate_metrics,
    categorize_errors,
    evaluate,
    flatten_entities,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_assignment_data():
    path = PROJECT_ROOT / "data" / "raw" / "entity_extraction.json"

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def test_assignment_strict_metrics():
    report = evaluate(load_assignment_data())

    assert report["strict"]["true_positives"] == 2
    assert report["strict"]["false_positives"] == 1
    assert report["strict"]["false_negatives"] == 1

    assert report["strict"]["precision"] == 0.667
    assert report["strict"]["recall"] == 0.667
    assert report["strict"]["f1"] == 0.667


def test_assignment_lenient_metrics():
    report = evaluate(load_assignment_data())

    assert report["lenient"]["true_positives"] == 3
    assert report["lenient"]["false_positives"] == 0
    assert report["lenient"]["false_negatives"] == 0

    assert report["lenient"]["precision"] == 1.0
    assert report["lenient"]["recall"] == 1.0
    assert report["lenient"]["f1"] == 1.0


def test_denver_is_identified_as_wrong_type():
    report = evaluate(load_assignment_data())

    assert report["errors"]["wrong_type"] == [
        {
            "entity": "denver",
            "expected_types": ["location"],
            "predicted_types": ["organization"],
        }
    ]


def test_per_type_metrics_identify_location_error():
    report = evaluate(load_assignment_data())

    assert report["per_type"]["person"]["f1"] == 1.0
    assert report["per_type"]["organization"]["f1"] == 0.667
    assert report["per_type"]["location"]["f1"] == 0.0


def test_missed_entity_is_reported():
    reference = {
        ("person", "maria gomez"),
        ("organization", "northwind logistics"),
    }

    predicted = {
        ("person", "maria gomez"),
    }

    errors = categorize_errors(
        reference,
        predicted,
        "Maria Gomez works at Northwind Logistics."
    )

    assert errors["missed"] == ["northwind logistics"]


def test_wrong_entity_boundary_is_reported():
    reference = {
        ("organization", "northwind logistics"),
    }

    predicted = {
        ("organization", "northwind"),
    }

    errors = categorize_errors(
        reference,
        predicted,
        "Northwind Logistics hired Maria Gomez."
    )

    assert errors["wrong_boundary"] == [
        {
            "predicted_entity": "northwind",
            "reference_entity": "northwind logistics",
        }
    ]
    assert errors["missed"] == []


def test_entity_not_present_in_text_is_invented():
    reference = {
        ("person", "maria gomez"),
    }

    predicted = {
        ("person", "maria gomez"),
        ("organization", "atlantis holdings"),
    }

    errors = categorize_errors(
        reference,
        predicted,
        "Maria Gomez attended the meeting."
    )

    assert errors["invented"] == ["atlantis holdings"]


def test_unannotated_entity_present_in_text_is_spurious():
    reference = {
        ("person", "maria gomez"),
    }

    predicted = {
        ("person", "maria gomez"),
        ("organization", "ceo"),
    }

    errors = categorize_errors(
        reference,
        predicted,
        "Maria Gomez is the CEO."
    )

    assert errors["spurious"] == ["ceo"]


def test_name_comparison_ignores_case_and_extra_spaces():
    reference = flatten_entities({
        "People": ["  Maria   Gomez "]
    })

    predicted = flatten_entities({
        "person": ["maria gomez"]
    })

    assert reference == predicted


def test_duplicate_entity_names_are_counted_once():
    entities = flatten_entities({
        "People": ["Maria Gomez", "Maria Gomez", "MARIA GOMEZ"]
    })

    assert len(entities) == 1


def test_empty_prediction_has_zero_recall():
    report = calculate_metrics(
        {"maria gomez"},
        set()
    )

    assert report["precision"] == 0.0
    assert report["recall"] == 0.0
    assert report["f1"] == 0.0


def test_empty_reference_and_prediction():
    report = calculate_metrics(set(), set())

    assert report["true_positives"] == 0
    assert report["false_positives"] == 0
    assert report["false_negatives"] == 0
    assert report["precision"] == 0.0
    assert report["recall"] == 0.0
    assert report["f1"] == 0.0


def test_unknown_entity_group_is_rejected():
    with pytest.raises(ValueError, match="Unknown entity group"):
        flatten_entities({
            "Products": ["CloudSync"]
        })


def test_missing_evaluation_field_is_rejected():
    with pytest.raises(ValueError, match="Missing evaluation fields"):
        evaluate({
            "article_id": "NEWS-002",
            "text": "Example article."
        })
