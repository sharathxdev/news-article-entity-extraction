import json
from pathlib import Path

import pytest

from src.graph.graph_builder import build_graph


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_graph_inputs():
    with (PROJECT_ROOT / "data/raw/entity_extraction.json").open() as file:
        article = json.load(file)

    with (PROJECT_ROOT / "data/raw/relationship_annotations.json").open() as file:
        annotations = json.load(file)

    return article, annotations


def test_graph_contains_four_expected_nodes():
    article, annotations = load_graph_inputs()

    graph = build_graph(article, annotations)

    labels = [node["label"] for node in graph["nodes"]]

    assert labels == ["Article", "Person", "Organization", "Location"]


def test_article_mentions_all_reference_entities():
    article, annotations = load_graph_inputs()

    graph = build_graph(article, annotations)

    assert len(graph["mentions"]) == 3

    mentioned = {
        (item["entity_label"], item["entity_name"])
        for item in graph["mentions"]
    }

    assert mentioned == {
        ("Person", "Maria Gomez"),
        ("Organization", "Northwind Logistics"),
        ("Location", "Denver"),
    }


def test_person_works_at_organization():
    article, annotations = load_graph_inputs()

    graph = build_graph(article, annotations)

    works_at = [
        relation for relation in graph["relationships"]
        if relation["type"] == "WORKS_AT"
    ]

    assert len(works_at) == 1
    assert works_at[0]["person"] == "Maria Gomez"
    assert works_at[0]["organization"] == "Northwind Logistics"
    assert works_at[0]["properties"]["role"] == "CEO"


def test_unsupported_location_relationship_is_not_created():
    article, annotations = load_graph_inputs()

    graph = build_graph(article, annotations)

    located_in = [
        relation for relation in graph["relationships"]
        if relation["type"] == "LOCATED_IN"
    ]

    assert located_in == []


def test_relationship_with_unreferenced_person_is_rejected():
    article, annotations = load_graph_inputs()

    annotations["works_at"][0]["person"] = "John Smith"

    with pytest.raises(ValueError, match="Person is not in the reference"):
        build_graph(article, annotations)


def test_relationship_without_article_evidence_is_rejected():
    article, annotations = load_graph_inputs()

    annotations["works_at"][0]["evidence"] = "Headquartered in Denver"

    with pytest.raises(ValueError, match="evidence does not appear"):
        build_graph(article, annotations)


def test_annotations_for_another_article_are_rejected():
    article, annotations = load_graph_inputs()

    annotations["article_id"] = "NEWS-999"

    with pytest.raises(ValueError, match="different article"):
        build_graph(article, annotations)
