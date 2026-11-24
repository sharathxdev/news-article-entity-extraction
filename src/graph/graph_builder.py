"""Prepare a knowledge graph from article reference annotations."""

from pathlib import Path
import json


ENTITY_LABELS = {
    "People": "Person",
    "Organizations": "Organization",
    "Locations": "Location",
}


def clean_name(value):
    """Remove unnecessary whitespace from an entity name."""
    return " ".join(value.split())


def build_graph(article, relationship_annotations):
    """
    Build graph nodes and relationships from reference annotations.

    LLM predictions are deliberately not used to create graph entities.
    Relationship annotations must be supported by article evidence.
    """
    article_id = article.get("article_id")
    text = article.get("text")
    reference = article.get("reference")

    if not article_id or not isinstance(text, str):
        raise ValueError("Article ID and article text are required.")

    if not isinstance(reference, dict):
        raise ValueError("Article reference must be a dictionary.")

    if relationship_annotations.get("article_id") != article_id:
        raise ValueError("Relationship annotations belong to a different article.")

    nodes = [
        {
            "label": "Article",
            "properties": {
                "article_id": article_id,
                "text": text,
            },
        }
    ]

    entities_by_type = {}

    # Create entity nodes from the reference annotations.
    for group_name, label in ENTITY_LABELS.items():
        names = reference.get(group_name, [])

        if not isinstance(names, list):
            raise ValueError(f"{group_name} must contain a list.")

        entities = {}
        for name in names:
            if not isinstance(name, str) or not clean_name(name):
                raise ValueError(f"Invalid entity name in {group_name}.")

            cleaned = clean_name(name)
            entities.setdefault(cleaned.casefold(), cleaned)

        entities_by_type[label] = entities

        for name in entities.values():
            nodes.append({
                "label": label,
                "properties": {"name": name},
            })

    mentions = []

    # Every reference entity is connected to its source article.
    for label, entities in entities_by_type.items():
        for name in entities.values():
            mentions.append({
                "article_id": article_id,
                "entity_label": label,
                "entity_name": name,
            })

    relationships = []

    # Person -> Organization.
    for relation in relationship_annotations.get("works_at", []):
        person = clean_name(relation["person"])
        organization = clean_name(relation["organization"])
        evidence = relation["evidence"]

        if person.casefold() not in entities_by_type["Person"]:
            raise ValueError(f"Person is not in the reference: {person}")

        if organization.casefold() not in entities_by_type["Organization"]:
            raise ValueError(
                f"Organization is not in the reference: {organization}"
            )

        if not isinstance(evidence, str) or evidence.casefold() not in text.casefold():
            raise ValueError("WORKS_AT evidence does not appear in the article.")

        relationships.append({
            "type": "WORKS_AT",
            "person": entities_by_type["Person"][person.casefold()],
            "organization": entities_by_type["Organization"][
                organization.casefold()
            ],
            "properties": {
                "role": relation.get("role"),
                "evidence": evidence,
            },
        })

    # Organization -> Location.
    # A relationship is added only when explicitly annotated and supported.
    for relation in relationship_annotations.get("located_in", []):
        organization = clean_name(relation["organization"])
        location = clean_name(relation["location"])
        evidence = relation["evidence"]

        if organization.casefold() not in entities_by_type["Organization"]:
            raise ValueError(
                f"Organization is not in the reference: {organization}"
            )

        if location.casefold() not in entities_by_type["Location"]:
            raise ValueError(f"Location is not in the reference: {location}")

        if not isinstance(evidence, str) or evidence.casefold() not in text.casefold():
            raise ValueError("LOCATED_IN evidence does not appear in the article.")

        relationships.append({
            "type": "LOCATED_IN",
            "organization": entities_by_type["Organization"][
                organization.casefold()
            ],
            "location": entities_by_type["Location"][location.casefold()],
            "properties": {"evidence": evidence},
        })

    return {
        "nodes": nodes,
        "mentions": mentions,
        "relationships": relationships,
    }


def main():
    project_root = Path(__file__).resolve().parents[2]

    article_file = project_root / "data" / "raw" / "entity_extraction.json"
    annotation_file = (
        project_root / "data" / "raw" / "relationship_annotations.json"
    )
    output_file = project_root / "outputs" / "graph_payload.json"

    with article_file.open("r", encoding="utf-8") as file:
        article = json.load(file)

    with annotation_file.open("r", encoding="utf-8") as file:
        annotations = json.load(file)

    graph = build_graph(article, annotations)

    output_file.parent.mkdir(parents=True, exist_ok=True)

    with output_file.open("w", encoding="utf-8") as file:
        json.dump(graph, file, indent=2)
        file.write("\n")

    print("===== GRAPH PREPARATION REPORT =====")
    print(f"Nodes: {len(graph['nodes'])}")
    print(f"Article mention relationships: {len(graph['mentions'])}")
    print(f"Other relationships: {len(graph['relationships'])}")

    for relationship in graph["relationships"]:
        print(
            f"{relationship['type']}: "
            f"{relationship.get('person', relationship.get('organization'))}"
            " -> "
            f"{relationship.get('organization', relationship.get('location'))}"
        )

    print(f"\nGraph data saved to: {output_file}")


if __name__ == "__main__":
    main()
