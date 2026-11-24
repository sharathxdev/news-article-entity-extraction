# News Article Entity Extraction

GitHub: https://github.com/sharathxdev/news-article-entity-extraction

I built this project for a news article entity extraction assignment. It covers
article cleaning, weekly topic counts, entity extraction evaluation and a
knowledge graph using Neo4j.

I started with the five article records and the Maria Gomez example supplied
in the assignment. I kept the input records in JSON files so the project can
be run without an external news API or an LLM API key.

## 1. Part A: Article cleaning

The input contains five records.

I found that the first two records have the same title. Their topic values
use different capitalization (`local` and `Local`), and their dates use
different formats.

My cleaning code:

- Removes extra whitespace from titles.
- Normalizes topic names to lowercase.
- Converts supported dates into ISO `YYYY-MM-DD` format.
- Removes duplicate titles without considering capitalization.
- Reports invalid records.
- Records ambiguous dates before duplicate removal.

I keep the first occurrence of a duplicate title because the assignment
does not provide unique article IDs. Two different articles can have the
same title in a larger dataset, so this is a limitation of the approach.

### Cleaning results

| Measure | Result |
|---|---:|
| Input records | 5 |
| Invalid records | 0 |
| Duplicate titles removed | 1 |
| Ambiguous dates flagged | 1 |
| Cleaned records | 4 |

The date `08/01/2026` can mean August 1 or January 8. I interpreted it as
August 1 because the duplicate record contains the ISO date `2026-08-01`.
I record the decision in the cleaning report rather than silently choosing
a format.

### Weekly topic counts

I used ISO calendar weeks, which include both the calendar year and the
week number.

| Calendar week | Topic | Article count |
|---|---|---:|
| 2026-W31 | local | 1 |
| 2026-W32 | business | 2 |
| 2026-W32 | sports | 1 |

The duplicate article is counted only once.

## 2. Part B.1: Entity extraction evaluation

The reference extraction contains:

- Person: Maria Gomez
- Organization: Northwind Logistics
- Location: Denver

The LLM finds all three names, but puts Denver under Organizations instead
of Locations.

I calculate strict precision, recall and F1 using both the entity name
and its type.

### Strict evaluation

| Metric | Result |
|---|---:|
| True positives | 2 |
| False positives | 1 |
| False negatives | 1 |
| Precision | 0.667 |
| Recall | 0.667 |
| F1 | 0.667 |

The formulas are:

- Precision = TP / (TP + FP)
- Recall = TP / (TP + FN)
- F1 = 2 × Precision × Recall / (Precision + Recall)

I also calculate lenient metrics by comparing entity names without
considering their types. Lenient precision, recall and F1 are all 1.0.

This comparison shows that the LLM found all three names, but made a
classification error.

### Which error matters more?

The wrong type matters because these extracted entities are used to build
a knowledge graph. If Denver is treated as an organization, organization
queries can return a location as if it were a company.

A missed entity also matters because information is left out of the graph.
However, a false fact can be more misleading to someone using the graph.

For this example, I would improve the entity typing before using the
extraction output to create graph nodes.

## 3. Part B.2: Knowledge graph

I use four node types:

- Article
- Person
- Organization
- Location

The graph relationships are:

```text
Article -[:MENTIONS]-> Person
Article -[:MENTIONS]-> Organization
Article -[:MENTIONS]-> Location
Person -[:WORKS_AT]-> Organization
```

The `WORKS_AT` relationship stores the role and evidence supporting it.

For this article, Maria Gomez works at Northwind Logistics as CEO. The
relationship evidence is taken from the sentence:

`Maria Gomez, CEO of Northwind Logistics`

I do not create a `LOCATED_IN` relationship between Northwind Logistics and
Denver. The article says that the company announced a partnership with the
city. It does not say that the company is located there.

I use the reference extraction to build the graph, not the incorrect LLM
entity types.

### Organization lookup query

The query is stored in:

`neo4j/queries/find_organizations_by_person.cypher`

```cypher
MATCH (person:Person {name: $person})
MATCH (article:Article)-[:MENTIONS]->(person)
MATCH (article)-[:MENTIONS]->(organization:Organization)

RETURN DISTINCT
    article.article_id AS article_id,
    organization.name AS organization

ORDER BY article_id, organization;
```

The person name is a parameter, so the same query works for different
people without changing the Cypher text.

I ran this query against my local Neo4j database.

For `Maria Gomez`, the result was:

```text
NEWS-001 | Northwind Logistics
```

An unknown person's name returns an empty result.

The loader creates uniqueness constraints and uses `MERGE` to avoid
creating duplicate nodes and relationships when the same article is
loaded again.

## 4. Project structure

```text
news-article-entity-extraction/
|
├── data/
│   ├── raw/
│   │   ├── articles.json
│   │   ├── entity_extraction.json
│   │   └── relationship_annotations.json
│   └── processed/
│       ├── cleaned_articles.json
│       ├── cleaning_report.json
│       └── weekly_topic_counts.json
|
├── neo4j/
│   └── queries/
│       └── find_organizations_by_person.cypher
|
├── outputs/
│   ├── entity_evaluation.json
│   ├── graph_payload.json
│   └── organization_lookup.json
|
├── src/
│   ├── data_cleaning.py
│   ├── date_utils.py
│   ├── entity_evaluation.py
│   ├── weekly_analysis.py
│   ├── pipeline.py
│   └── graph/
│       ├── graph_builder.py
│       └── neo4j_loader.py
|
├── tests/
├── requirements.txt
└── README.md
```

Generated reports in `outputs/` are ignored by Git and can be regenerated
by running the project.

## 5. How to run

I developed and tested this project with Python 3.13.

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the dependencies:

```bash
python -m pip install -r requirements.txt
```

Run the Python pipeline:

```bash
python -m src.pipeline
```

This runs article cleaning, weekly analysis, entity evaluation, graph
preparation and the automated tests. Neo4j is not required for this command.

To load the graph and execute the person lookup, start Neo4j and run:

```bash
python -m src.pipeline --load-neo4j --person "Maria Gomez"
```

The loader asks for the Neo4j password without displaying it.

The local Neo4j instance used during development listens on port `7688`.
For a different installation, set the Bolt address before running:

```bash
export NEO4J_URI="bolt://127.0.0.1:7687"
```

The default username and database are both `neo4j`. They can be changed
using `NEO4J_USER` and `NEO4J_DATABASE`.

To run only the tests:

```bash
python -m pytest -q
```

Use the virtual environment's Python interpreter if the shell has another
Python environment active.

## 6. Limitations and next steps

This assignment contains only five article records and one entity extraction
example. The evaluation demonstrates the calculations on the supplied
example, but it is not enough to claim general model performance.

With a larger dataset, I would:

- Use stable article and entity IDs instead of relying only on names.
- Review duplicate titles before treating them as the same article.
- Define date-format rules for each source.
- Build a larger manually labelled entity extraction test set.
- Store entity character positions for exact span evaluation.
- Add relationship types only when the source text supports them.

The current graph is deliberately small and uses the reference annotations.
This avoids turning the incorrect Denver entity type into a false
organization node.

## 7. AI tool usage

I used ChatGPT as a programming assistant while working through Python,
pytest and Neo4j implementation issues. I reviewed the code, ran tests,
checked the expected results against the assignment data and tested the
query against my local Neo4j database.

I documented the choices I made for duplicate handling, date interpretation,
entity evaluation and graph relationships because I need to be able to
explain these decisions and their limitations.

## 8. Repository

https://github.com/sharathxdev/news-article-entity-extraction
