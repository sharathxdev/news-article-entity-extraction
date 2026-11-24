"""Evaluate named-entity extraction against reference annotations."""

import json
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = PROJECT_ROOT / "data" / "raw" / "entity_extraction.json"
OUTPUT_FILE = PROJECT_ROOT / "outputs" / "entity_evaluation.json"

ENTITY_TYPES = ("person", "organization", "location")

GROUP_TO_TYPE = {
    "person": "person",
    "people": "person",
    "organization": "organization",
    "organizations": "organization",
    "location": "location",
    "locations": "location",
}


def normalize_name(name):
    """Normalize an entity name for case-insensitive comparison."""
    return " ".join(name.split()).casefold()


def flatten_entities(groups):
    """
    Convert grouped entities into a set of (type, normalized_name).

    Example:
        {"People": ["Maria Gomez"]}

    becomes:
        {("person", "maria gomez")}
    """
    if not isinstance(groups, dict):
        raise ValueError("Entity groups must be a dictionary.")

    flattened = set()

    for group_name, names in groups.items():
        group_key = group_name.strip().casefold()

        if group_key not in GROUP_TO_TYPE:
            raise ValueError(f"Unknown entity group: {group_name!r}")

        if not isinstance(names, list):
            raise ValueError(
                f"Entities in {group_name!r} must be provided as a list."
            )

        entity_type = GROUP_TO_TYPE[group_key]

        for name in names:
            if not isinstance(name, str):
                raise ValueError(
                    f"Entity names in {group_name!r} must be strings."
                )

            normalized = normalize_name(name)

            if normalized:
                flattened.add((entity_type, normalized))

    return flattened


def calculate_metrics(reference, predicted):
    """Calculate precision, recall and F1 for two sets."""
    true_positives = len(reference & predicted)
    false_positives = len(predicted - reference)
    false_negatives = len(reference - predicted)

    precision = (
        true_positives / (true_positives + false_positives)
        if true_positives + false_positives
        else 0.0
    )

    recall = (
        true_positives / (true_positives + false_negatives)
        if true_positives + false_negatives
        else 0.0
    )

    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )

    return {
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
    }


def contains_entity(text, entity):
    """Check for a complete entity phrase, not just a partial substring."""
    pattern = r"(?<!\w)" + re.escape(entity) + r"(?!\w)"
    return re.search(pattern, text) is not None


def find_boundary_match(name, reference_names):
    """
    Find a reference name that differs only by a partial entity boundary.

    Example:
        Predicted: Northwind
        Reference: Northwind Logistics
    """
    for reference_name in sorted(reference_names):
        if (
            contains_entity(reference_name, name)
            or contains_entity(name, reference_name)
        ):
            return reference_name

    return None


def categorize_errors(reference, predicted, article_text):
    """
    Explain why predictions differ from the reference.

    Wrong type:
        Same name, incorrect entity type.

    Wrong boundary:
        An incomplete or extended version of a reference entity.

    Missed:
        Reference entity not represented in the prediction.

    Spurious:
        Predicted entity appears in the text but is absent from reference.

    Invented:
        Predicted entity cannot be found in the article text.
    """
    reference_by_name = {}
    predicted_by_name = {}

    for entity_type, name in reference:
        reference_by_name.setdefault(name, set()).add(entity_type)

    for entity_type, name in predicted:
        predicted_by_name.setdefault(name, set()).add(entity_type)

    normalized_text = normalize_name(article_text)

    errors = {
        "wrong_type": [],
        "wrong_boundary": [],
        "missed": [],
        "spurious": [],
        "invented": [],
    }

    represented_reference_names = set()

    # Examine every predicted entity.
    for name, predicted_types in predicted_by_name.items():

        if name in reference_by_name:
            expected_types = reference_by_name[name]
            represented_reference_names.add(name)

            if predicted_types != expected_types:
                errors["wrong_type"].append({
                    "entity": name,
                    "expected_types": sorted(expected_types),
                    "predicted_types": sorted(predicted_types),
                })

            continue

        # Check whether the prediction is a partial or extended name.
        boundary_match = find_boundary_match(
            name,
            set(reference_by_name)
        )

        if boundary_match is not None:
            represented_reference_names.add(boundary_match)

            errors["wrong_boundary"].append({
                "predicted_entity": name,
                "reference_entity": boundary_match,
            })

        elif contains_entity(normalized_text, name):
            errors["spurious"].append(name)

        else:
            errors["invented"].append(name)

    # Reference entities not represented in any prediction are missed.
    for name in sorted(set(reference_by_name) - represented_reference_names):
        errors["missed"].append(name)

    return errors


def evaluate(data):
    """Evaluate one article's LLM extraction against its reference."""
    required_fields = {
        "article_id",
        "text",
        "reference",
        "llm_output",
    }

    missing_fields = required_fields - set(data)

    if missing_fields:
        raise ValueError(
            f"Missing evaluation fields: {sorted(missing_fields)}"
        )

    if not isinstance(data["text"], str):
        raise ValueError("Article text must be a string.")

    reference = flatten_entities(data["reference"])
    predicted = flatten_entities(data["llm_output"])

    # Strict evaluation: entity name AND entity type must match.
    strict = calculate_metrics(reference, predicted)

    # Lenient evaluation: compare names without considering entity types.
    reference_names = {name for _, name in reference}
    predicted_names = {name for _, name in predicted}

    lenient = calculate_metrics(reference_names, predicted_names)

    # Calculate metrics separately for each entity type.
    per_type = {}

    for entity_type in ENTITY_TYPES:
        reference_type = {
            entity for entity in reference
            if entity[0] == entity_type
        }

        predicted_type = {
            entity for entity in predicted
            if entity[0] == entity_type
        }

        per_type[entity_type] = calculate_metrics(
            reference_type,
            predicted_type
        )

    errors = categorize_errors(
        reference,
        predicted,
        data["text"]
    )

    return {
        "article_id": data["article_id"],
        "strict": strict,
        "lenient": lenient,
        "per_type": per_type,
        "errors": errors,
    }


def main():
    with INPUT_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)

    report = evaluate(data)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2)
        file.write("\n")

    print("\n===== ENTITY EXTRACTION EVALUATION =====")
    print(json.dumps(report, indent=2))

    print(f"\nEvaluation saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
