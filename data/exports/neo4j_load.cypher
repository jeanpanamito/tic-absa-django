// Ajusta los nombres de archivo si los renombraste.
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Concept) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (s:ConceptScheme) REQUIRE s.id IS UNIQUE;

// Cargar nodos
LOAD CSV WITH HEADERS FROM 'file:///neo4j_nodes.csv' AS row FIELDTERMINATOR ','
WITH row, split(row[':LABEL'], ';') AS labels
CALL { WITH row RETURN row[':ID'] AS id, row.prefLabel AS prefLabel, row.definition AS definition, row.note AS note, row.inScheme AS inScheme }
CALL apoc.create.node(labels, {id: id, prefLabel: prefLabel, definition: definition, note: note, inScheme: inScheme}) YIELD node
RETURN count(*) AS createdNodes;

// Cargar relaciones
LOAD CSV WITH HEADERS FROM 'file:///neo4j_rels.csv' AS row FIELDTERMINATOR ','
MATCH (a {id: row[':START_ID']}), (b {id: row[':END_ID']})
CALL apoc.create.relationship(a, row[':TYPE'], {}, b) YIELD rel
RETURN count(*) AS createdRels;
