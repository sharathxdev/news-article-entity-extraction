import json
from pathlib import Path

import pytest

from src.graph.graph_builder import build_graph
from src.graph.neo4j_loader import (
    DATABASE,
    LOAD_WORKS_AT,
    MENTION_QUERIES,
    QUERY_FILE,
    SCHEMA_QUERIES,
    find_organizations_by_person,
    load_graph,
    prepare_graph_data,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FakeDriver:
    """Record loading calls without requiring a running Neo4j server."""

    def __init__(self):
        self.calls = []

    def execute_query(self, query, **parameters):
        self.calls.append((query, parameters))
        return [], None, []


class QueryFakeDriver:
    """Return a controlled result for the organization lookup query."""

    def __init__(self):
        self.calls = []

    def execute_query(self, query, **parameters):
        self.calls.append((query, parameters))
        return [{"organization": "Northwind Logistics"}], None, []


@pytest.fixture
def graph_payload():
    article_path = PROJECT_ROOT / "data/raw/entity_extraction.json"
    annotation_path = (
        PROJECT_ROOT / "data/raw/relationship_annotations.json"
    )

    article = json.loads(article_path.read_text(encoding="utf-8"))
    annotations = json.loads(annotation_path.read_text(encoding="utf-8"))

    return build_graph(article, annotations)


def test_prepare_graph_data_has_expected_entities(graph_payload):
    data = prepare_graph_data(graph_payload)

    assert data["article_id"] == "NEWS-001"
    assert len(data["mentions"]["Person"]) == 1
    assert len(data["mentions"]["Organization"]) == 1
    assert len(data["mentions"]["Location"]) == 1

    assert data["mentions"]["Person"][0]["entity_name"] == "Maria Gomez"
    assert (
        data["mentions"]["Organization"][0]["entity_name"]
        == "Northwind Logistics"
    )
    assert data["mentions"]["Location"][0]["entity_name"] == "Denver"


def test_loader_creates_expected_graph(graph_payload):
    driver = FakeDriver()

    report = load_graph(driver, graph_payload)

    assert report == {
        "articles_loaded": 1,
        "entities_loaded": 3,
        "mentions_loaded": 3,
        "relationships_loaded": 1,
    }

    assert len(driver.calls) == 9


def test_loader_uses_unique_constraints(graph_payload):
    driver = FakeDriver()

    load_graph(driver, graph_payload)

    schema_calls = driver.calls[:len(SCHEMA_QUERIES)]

    assert len(schema_calls) == 4

    for query, parameters in schema_calls:
        assert "IF NOT EXISTS" in query
        assert parameters["database_"] == DATABASE


def test_loader_creates_three_mention_relationships(graph_payload):
    driver = FakeDriver()

    load_graph(driver, graph_payload)

    mention_calls = [
        (query, parameters)
        for query, parameters in driver.calls
        if "[:MENTIONS]" in query
    ]

    assert len(mention_calls) == 3


def test_loader_preserves_work_relationship_evidence(graph_payload):
    driver = FakeDriver()

    load_graph(driver, graph_payload)

    work_call = next(
        (query, parameters)
        for query, parameters in driver.calls
        if "WORKS_AT" in query
    )

    assert work_call[1]["rows"] == [{
        "person": "Maria Gomez",
        "organization": "Northwind Logistics",
        "role": "CEO",
        "evidence": "Maria Gomez, CEO of Northwind Logistics",
    }]


def test_loader_does_not_invent_located_in_relationship(graph_payload):
    driver = FakeDriver()

    report = load_graph(driver, graph_payload)

    assert report["relationships_loaded"] == 1

    executed_queries = [query for query, _ in driver.calls]

    assert not any(
        "LOCATED_IN" in query for query in executed_queries
    )


def test_unknown_entity_label_is_rejected(graph_payload):
    graph_payload["mentions"].append({
        "article_id": "NEWS-001",
        "entity_label": "Company",
        "entity_name": "Example Company",
    })

    driver = FakeDriver()

    with pytest.raises(ValueError, match="Unsupported entity label"):
        load_graph(driver, graph_payload)

    assert driver.calls == []


def test_person_query_file_uses_parameter():
    query = QUERY_FILE.read_text(encoding="utf-8")

    assert "$person" in query
    assert "MATCH (person:Person" in query
    assert "Organization" in query
    assert "Maria Gomez" not in query


def test_organization_lookup_uses_person_parameter():
    driver = QueryFakeDriver()

    results = find_organizations_by_person(
        driver,
        "  Maria Gomez  ",
    )

    assert results == ["Northwind Logistics"]
    assert len(driver.calls) == 1

    query, parameters = driver.calls[0]

    assert "$person" in query
    assert parameters["person"] == "Maria Gomez"
    assert parameters["database_"] == DATABASE


def test_organization_lookup_rejects_empty_person():
    driver = QueryFakeDriver()

    with pytest.raises(ValueError, match="non-empty"):
        find_organizations_by_person(driver, "  ")

    assert driver.calls == []
