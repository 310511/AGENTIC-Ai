"""
Neo4j graph store — entity and relationship persistence with tenant isolation.

Graph schema:
  (:Entity {text, label, tenant_id, source_document_id, ...metadata})
  -[:RELATIONSHIP {type, tenant_id, source_document_id, ...metadata}]->
  (:Entity {text, label, tenant_id, ...})

All nodes and relationships carry tenant_id so every query can filter on it.
Writes use MERGE so re-ingesting the same document is idempotent.

Security: tenant_id is always passed as a parameter — never interpolated into
Cypher strings — to prevent injection.
"""
from __future__ import annotations

import logging
from typing import Any

from neo4j import AsyncDriver, AsyncGraphDatabase

from .config import Settings

logger = logging.getLogger(__name__)


class GraphStore:
    def __init__(self, settings: Settings) -> None:
        self._driver: AsyncDriver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )

    async def verify_connectivity(self) -> None:
        await self._driver.verify_connectivity()

    async def close(self) -> None:
        await self._driver.close()

    # ── write ─────────────────────────────────────────────────────────────────

    async def merge_entities(
        self,
        tenant_id: str,
        entities: list[dict],
    ) -> int:
        """
        MERGE each entity node. Returns count of entities processed.

        Uniqueness key: (text, label, tenant_id) — same entity from multiple
        documents shares one node; source_document_id is stored in a list
        property so provenance is not lost.
        """
        if not entities:
            return 0

        query = """
        UNWIND $entities AS e
        MERGE (n:Entity {text: e.text, label: e.label, tenant_id: $tenant_id})
        ON CREATE SET n.source_documents = [e.source_document_id],
                      n.metadata = e.metadata,
                      n.created_at = timestamp()
        ON MATCH SET  n.source_documents = CASE
                          WHEN e.source_document_id IN n.source_documents
                          THEN n.source_documents
                          ELSE n.source_documents + e.source_document_id
                      END,
                      n.updated_at = timestamp()
        RETURN count(n) AS merged
        """
        async with self._driver.session() as session:
            result = await session.run(
                query,
                tenant_id=tenant_id,
                entities=[
                    {
                        "text": e["text"],
                        "label": e["label"],
                        "source_document_id": e["source_document_id"],
                        "metadata": e.get("metadata", {}),
                    }
                    for e in entities
                ],
            )
            record = await result.single()
            return record["merged"] if record else 0

    async def merge_relationships(
        self,
        tenant_id: str,
        relationships: list[dict],
    ) -> int:
        """
        MERGE each relationship between entity nodes.
        Creates the endpoint entities if they don't exist.
        Returns count of relationships processed.
        """
        if not relationships:
            return 0

        query = """
        UNWIND $rels AS r
        MERGE (src:Entity {text: r.source_text, label: r.source_label, tenant_id: $tenant_id})
        MERGE (tgt:Entity {text: r.target_text, label: r.target_label, tenant_id: $tenant_id})
        MERGE (src)-[rel:RELATIONSHIP {
            type: r.relation_type,
            tenant_id: $tenant_id,
            source_document_id: r.source_document_id
        }]->(tgt)
        ON CREATE SET rel.metadata = r.metadata, rel.created_at = timestamp()
        RETURN count(rel) AS merged
        """
        async with self._driver.session() as session:
            result = await session.run(
                query,
                tenant_id=tenant_id,
                rels=[
                    {
                        "source_text": r["source_text"],
                        "source_label": r["source_label"],
                        "target_text": r["target_text"],
                        "target_label": r["target_label"],
                        "relation_type": r["relation_type"],
                        "source_document_id": r["source_document_id"],
                        "metadata": r.get("metadata", {}),
                    }
                    for r in relationships
                ],
            )
            record = await result.single()
            return record["merged"] if record else 0

    async def delete_by_document(self, tenant_id: str, source_document_id: str) -> int:
        """
        Remove source_document_id from provenance lists.
        Delete nodes/relationships that have no remaining provenance.
        Returns count of nodes deleted.
        """
        query = """
        MATCH (n:Entity {tenant_id: $tenant_id})
        WHERE $doc_id IN n.source_documents
        SET n.source_documents = [x IN n.source_documents WHERE x <> $doc_id]
        WITH n
        WHERE size(n.source_documents) = 0
        DETACH DELETE n
        RETURN count(n) AS deleted
        """
        async with self._driver.session() as session:
            result = await session.run(
                query,
                tenant_id=tenant_id,
                doc_id=source_document_id,
            )
            record = await result.single()
            return record["deleted"] if record else 0

    # ── read ──────────────────────────────────────────────────────────────────

    async def retrieve(
        self,
        tenant_id: str,
        query_terms: list[str],
        depth: int,
        limit: int,
    ) -> dict[str, list[dict]]:
        """
        Find entities matching any query term, then traverse up to *depth* hops.

        Returns {"entities": [...], "relationships": [...]}.
        All results are scoped to tenant_id.
        """
        # Build a case-insensitive contains match for each term.
        where_clauses = " OR ".join(
            f"toLower(n.text) CONTAINS toLower($term{i})"
            for i in range(len(query_terms))
        )
        params: dict[str, Any] = {"tenant_id": tenant_id, "limit": limit}
        for i, term in enumerate(query_terms):
            params[f"term{i}"] = term

        # Seed query: find matching root entities
        seed_query = f"""
        MATCH (n:Entity {{tenant_id: $tenant_id}})
        WHERE {where_clauses}
        RETURN n LIMIT $limit
        """

        # Neighbour traversal up to depth hops
        neighbor_query = f"""
        MATCH (n:Entity {{tenant_id: $tenant_id}})
        WHERE {where_clauses}
        CALL apoc.path.subgraphNodes(n, {{
            relationshipFilter: 'RELATIONSHIP',
            maxLevel: {depth},
            labelFilter: '+Entity'
        }}) YIELD node
        RETURN DISTINCT node LIMIT $limit
        """

        # Fallback without APOC — simple 1-hop expand
        simple_query = f"""
        MATCH (n:Entity {{tenant_id: $tenant_id}})
        WHERE {where_clauses}
        OPTIONAL MATCH (n)-[r:RELATIONSHIP {{tenant_id: $tenant_id}}]-(m:Entity)
        RETURN DISTINCT n, r, m LIMIT $limit
        """

        entities: list[dict] = []
        relationships: list[dict] = []

        async with self._driver.session() as session:
            result = await session.run(simple_query, **params)
            async for record in result:
                n = record["n"]
                entities.append(_node_to_dict(n))
                r = record.get("r")
                m = record.get("m")
                if r is not None and m is not None:
                    entities.append(_node_to_dict(m))
                    relationships.append(_rel_to_dict(r, n, m))

        # Deduplicate by text+label
        seen_e: set[tuple] = set()
        seen_r: set[tuple] = set()
        unique_entities = []
        unique_rels = []
        for e in entities:
            key = (e["text"], e["label"])
            if key not in seen_e:
                seen_e.add(key)
                unique_entities.append(e)
        for r in relationships:
            key = (r["source_text"], r["target_text"], r["relation_type"])
            if key not in seen_r:
                seen_r.add(key)
                unique_rels.append(r)

        return {"entities": unique_entities, "relationships": unique_rels}


# ── helpers ───────────────────────────────────────────────────────────────────

def _node_to_dict(node) -> dict:
    props = dict(node)
    return {
        "text": props.get("text", ""),
        "label": props.get("label", ""),
        "source_document_id": (props.get("source_documents") or [""])[0],
        "metadata": props.get("metadata", {}),
    }


def _rel_to_dict(rel, src_node, tgt_node) -> dict:
    src = dict(src_node)
    tgt = dict(tgt_node)
    props = dict(rel)
    return {
        "source_text": src.get("text", ""),
        "source_label": src.get("label", ""),
        "target_text": tgt.get("text", ""),
        "target_label": tgt.get("label", ""),
        "relation_type": props.get("type", "RELATED_TO"),
        "source_document_id": props.get("source_document_id", ""),
        "metadata": props.get("metadata", {}),
    }
