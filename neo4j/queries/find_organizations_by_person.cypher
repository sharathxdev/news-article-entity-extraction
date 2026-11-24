MATCH (person:Person {name: $person})
MATCH (article:Article)-[:MENTIONS]->(person)
MATCH (article)-[:MENTIONS]->(organization:Organization)

RETURN DISTINCT
    article.article_id AS article_id,
    organization.name AS organization

ORDER BY article_id, organization;
