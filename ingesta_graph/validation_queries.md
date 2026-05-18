# Validation Queries for SKOS Graph

Use these queries in Neo4j Browser or Bloom to validate that `src/rag/neo4j_ingest.py` has correctly populated the graph.

## 1. Ontology & Schemes

**Check Concept Schemes**  
Verify that the main schemes (Aspects, Courses, etc.) exist.
```cypher
MATCH (s:ConceptScheme) 
RETURN s.id, s.prefLabel
```

**Check Aspect Hierarchy (Tree Structure)**  
Visualizes the tree of Aspects (root to leaves).
```cypher
MATCH (root:Concept:Aspect)
WHERE NOT (root)-[:BROADER]->(:Concept:Aspect)
OPTIONAL MATCH path = (root)<-[:BROADER*]-(child:Concept:Aspect)
RETURN root.prefLabel, child.prefLabel, length(path) as depth
ORDER BY depth
```

**Check Semantic Relations (Non-Hierarchical)**  
Verify relations like `related_to`, `uses`, etc. mapped to `RELATED`.
```cypher
MATCH (a:Concept:Aspect)-[r:RELATED]->(b:Concept:Aspect)
RETURN a.prefLabel as AspectA, type(r) as Rel, b.prefLabel as AspectB
LIMIT 20
```

## 2. Ingestion Data Integrity

**Check Comment Ingestion & SKOS Labels**  
Verify comments have the correct labels and properties.
```cypher
MATCH (c:Concept:Comment)
RETURN c.id, labels(c), c.text, c.sentiment
LIMIT 5
```

**Check Course Hierarchy**  
Verify the path from Comment -> Thread -> CourseEdition -> CourseBase.
```cypher
MATCH path = (c:Concept:Comment)-[:BROADER]->(t:Thread)-[:BROADER]->(ce:CourseEdition)-[:BROADER]->(cb:Concept:CourseBase)
RETURN path
LIMIT 5
```

## 3. Explicit Links (MENTIONS)

**Check Comments linked to Aspects**  
Most critical query for RAG: validating that unstructured text is linked to structured ontology nodes.
```cypher
MATCH (c:Concept:Comment)-[r:MENTIONS]->(a:Concept:Aspect)
RETURN c.text as Comment, r.sentiment as Sentiment, a.prefLabel as Aspect, a.definition
LIMIT 10
```

**Orphan Analysis**  
Find comments that were NOT linked to any Aspect (this might be expected if aspect extraction failed, but good to know stats).
```cypher
MATCH (c:Concept:Comment)
WHERE NOT (c)-[:MENTIONS]->(:Concept:Aspect)
RETURN count(c) as OrphanComments
```

## 4. Vector Index

**Verify Embeddings**
Check if embeddings are populated.
```cypher
MATCH (c:Concept:Comment)
WHERE c.embedding IS NOT NULL
RETURN count(c) as CommentsWithEmbeddings
```

## 5. Global Statistics

**Counts by Label**
```cypher
MATCH (n)
RETURN labels(n) as Labels, count(*) as Count
ORDER BY Count DESC
```

**Counts by Relationship Type**
```cypher
MATCH ()-[r]->()
RETURN type(r) as Relationship, count(*) as Count
ORDER BY Count DESC
```
