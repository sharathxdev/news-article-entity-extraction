"""Load news article entities into Neo4j and query related organizations."""

import argparse
import json
import os
from getpass import getpass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

GRAPH_FILE = PROJECT_ROOT / "outputs" / "graph_payload.json"
QUERY_FILE = (
    PROJECT_ROOT / "neo4j" / "queries"
    / "find_organizations_by_person.cypher"
)
RESULT_FILE = PROJECT_ROOT / "outputs" / "organization_lookup.json"

DATABASE = "neo4j"

SCHEMA_QUERIES = [
    """
    CREATE CONSTRAINT article_id_unique IF NOT EXISTS
    FOR (a:Article) REQUIRE a.article_id IS UNIQUE
    """,
    """
    CREATE CONSTRAINT person_name_unique IF NOT EXISTS
    FOR (p:Person) REQUIRE p.name IS UNIQUE
    """,
    """
    CREATE CONSTRAINT organization_name_unique IF NOT EXISTS
    FOR (o:Organization) REQUIRE o.name IS UNIQUE
    """,
    """
    CREATE CONSTRAINT location_name_unique IF NOT EXISTS
    FOR (l:Location) REQUIRE l.name IS UNIQUE
    """,
]

LOAD_ARTICLE = """
MERGE (a:Article {article_id: $article_id})
SET a.text = $text
"""

MENTION_QUERIES = {
    "Person": """
        UNWIND $rows AS row
        MATCH (a:Article {article_id: row.article_id})
        MERGE (p:Person {name: row.entity_name})
        MERGE (a)-[:MENTIONS]->(p)
    """,
    "Organization": """
        UNWIND $rows AS row
        MATCH (a:Article {article_id: row.article_id})
        MERGE (o:Organization {name: row.entity_name})
        MERGE (a)-[:MENTIONS]->(o)
    """,
    "Location": """
        UNWIND $rows AS row
        MATCH (a:Article {article_id: row.article_id})
        MERGE (l:Location {name: row.entity_name})
        MERGE (a)-[:MENTIONS]->(l)
    """,
}

LOAD_WORKS_AT = """
UNWIND $rows AS row
MATCH (p:Person {name: row.person})
MATCH (o:Organization {name: row.organization})
MERGE (p)-[r:WORKS_AT]->(o)
SET r.role = row.role,
    r.evidence = row.evidence
"""

LOAD_LOCATED_IN = """
UNWIND $rows AS row
MATCH (o:Organization {name: row.organization})
MATCH (l:Location {name: row.location})
MERGE (o)-[r:LOCATED_IN]->(l)
SET r.evidence = row.evidence
"""


def prepare_graph_data(graph):
    """Validate the graph payload before sending records to Neo4j."""

    if not isinstance(graph, dict):
        raise ValueError("Graph payload must be a dictionary.")

    nodes = graph.get("nodes")
    mentions = graph.get("mentions")
    relationships = graph.get("relationships")

    if not all(
        isinstance(value, list)
        for value in (nodes, mentions, relationships)
    ):
        raise ValueError("Nodes, mentions and relationships must be lists.")

    articles = [
        node for node in nodes
        if isinstance(node, dict) and node.get("label") == "Article"
    ]

    if len(articles) != 1:
        raise ValueError("Exactly one Article node is required.")

    properties = articles[0].get("properties", {})
    article_id = properties.get("article_id")
    article_text = properties.get("text")

    if not isinstance(article_id, str) or not article_id.strip():
        raise ValueError("Article ID is required.")

    if not isinstance(article_text, str) or not article_text.strip():
        raise ValueError("Article text is required.")

    grouped_mentions = {
        label: [] for label in MENTION_QUERIES
    }

    for mention in mentions:
        if not isinstance(mention, dict):
            raise ValueError("Each mention must be a dictionary.")

        label = mention.get("entity_label")
        name = mention.get("entity_name")

        if label not in grouped_mentions:
            raise ValueError(f"Unsupported entity label: {label!r}")

        if mention.get("article_id") != article_id:
            raise ValueError("Mention belongs to another article.")

        if not isinstance(name, str) or not name.strip():
            raise ValueError("Mention entity name cannot be empty.")

        grouped_mentions[label].append({
            "article_id": article_id,
            "entity_name": name.strip(),
        })

    works_at_rows = []
    located_in_rows = []

    for relationship in relationships:
        if not isinstance(relationship, dict):
            raise ValueError("Each relationship must be a dictionary.")

        relation_type = relationship.get("type")
        properties = relationship.get("properties", {})

        if not isinstance(properties, dict):
            raise ValueError("Relationship properties must be a dictionary.")

        evidence = properties.get("evidence")

        if not isinstance(evidence, str) or not evidence.strip():
            raise ValueError("Relationship evidence is required.")

        if relation_type == "WORKS_AT":
            works_at_rows.append({
                "person": relationship["person"],
                "organization": relationship["organization"],
                "role": properties.get("role"),
                "evidence": evidence,
            })

        elif relation_type == "LOCATED_IN":
            located_in_rows.append({
                "organization": relationship["organization"],
                "location": relationship["location"],
                "evidence": evidence,
            })

        else:
            raise ValueError(
                f"Unsupported relationship type: {relation_type!r}"
            )

    return {
        "article_id": article_id,
        "article_text": article_text,
        "mentions": grouped_mentions,
        "works_at": works_at_rows,
        "located_in": located_in_rows,
    }


def load_graph(driver, graph, database=DATABASE):
    """Load nodes and evidence-supported relationships into Neo4j."""

    data = prepare_graph_data(graph)

    for query in SCHEMA_QUERIES:
        driver.execute_query(query, database_=database)

    driver.execute_query(
        LOAD_ARTICLE,
        article_id=data["article_id"],
        text=data["article_text"],
        database_=database,
    )

    for label, rows in data["mentions"].items():
        if rows:
            driver.execute_query(
                MENTION_QUERIES[label],
                rows=rows,
                database_=database,
            )

    if data["works_at"]:
        driver.execute_query(
            LOAD_WORKS_AT,
            rows=data["works_at"],
            database_=database,
        )

    if data["located_in"]:
        driver.execute_query(
            LOAD_LOCATED_IN,
            rows=data["located_in"],
            database_=database,
        )

    entity_count = sum(
        len(rows) for rows in data["mentions"].values()
    )

    return {
        "articles_loaded": 1,
        "entities_loaded": entity_count,
        "mentions_loaded": entity_count,
        "relationships_loaded": (
            len(data["works_at"]) + len(data["located_in"])
        ),
    }


def find_organizations_by_person(driver, person, database=DATABASE):
    """Find organizations mentioned in articles containing a person."""

    if not isinstance(person, str) or not person.strip():
        raise ValueError("Person name must be a non-empty string.")

    if not QUERY_FILE.exists():
        raise FileNotFoundError(QUERY_FILE)

    query = QUERY_FILE.read_text(encoding="utf-8")

    records, _, _ = driver.execute_query(
        query,
        person=person.strip(),
        database_=database,
    )

    return [record["organization"] for record in records]


def main():
    parser = argparse.ArgumentParser(
        description="Load and query the news article knowledge graph."
    )

    parser.add_argument(
        "--person",
        default="Maria Gomez",
        help="Person whose co-mentioned organizations should be found.",
    )

    args = parser.parse_args()

    if not GRAPH_FILE.exists():
        raise SystemExit(
            "Graph payload missing. Run the graph builder first."
        )

    password = os.environ.get("NEO4J_PASSWORD")

    if not password:
        password = getpass("Enter Neo4j password: ")

    if not password:
        raise SystemExit("Neo4j password cannot be empty.")

    uri = os.environ.get(
        "NEO4J_URI",
        "bolt://127.0.0.1:7688",
    )
    username = os.environ.get("NEO4J_USER", "neo4j")
    database = os.environ.get("NEO4J_DATABASE", DATABASE)

    from neo4j import GraphDatabase

    graph = json.loads(
        GRAPH_FILE.read_text(encoding="utf-8")
    )

    print(f"Connecting to {uri}...")

    with GraphDatabase.driver(
        uri,
        auth=(username, password),
    ) as driver:

        driver.verify_connectivity()

        report = load_graph(
            driver,
            graph,
            database=database,
        )

        organizations = find_organizations_by_person(
            driver,
            args.person,
            database=database,
        )

    result = {
        "person": args.person,
        "organizations": organizations,
        "loading_report": report,
    }

    RESULT_FILE.parent.mkdir(parents=True, exist_ok=True)

    RESULT_FILE.write_text(
        json.dumps(result, indent=2) + "\n",
        encoding="utf-8",
    )

    print("\n===== NEO4J GRAPH LOADING REPORT =====")

    for key, value in report.items():
        print(f"{key}: {value}")

    print("\n===== ORGANIZATION LOOKUP =====")
    print(f"Person: {args.person}")
    print(f"Organizations: {organizations}")
    print(f"\nResult saved to: {RESULT_FILE}")


if __name__ == "__main__":
    main()
