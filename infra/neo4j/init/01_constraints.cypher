// ============================================================
// Graph Memory — Neo4j schema constraints and indexes
//
// Run once after Neo4j starts:
//   cypher-shell -u neo4j -p <password> < infra/neo4j/init/01_constraints.cypher
//
// Or from the Neo4j Browser (http://localhost:7474) paste each block.
// ============================================================

// Uniqueness constraint — one node per (text, label, tenant_id) triple.
// Also creates an index on these three properties automatically.
CREATE CONSTRAINT entity_unique IF NOT EXISTS
  FOR (n:Entity)
  REQUIRE (n.text, n.label, n.tenant_id) IS NODE KEY;

// Index tenant_id alone for fast tenant-scoped scans.
CREATE INDEX entity_tenant IF NOT EXISTS
  FOR (n:Entity)
  ON (n.tenant_id);

// Full-text index for substring/keyword search on entity text.
CREATE FULLTEXT INDEX entity_text IF NOT EXISTS
  FOR (n:Entity)
  ON EACH [n.text];
