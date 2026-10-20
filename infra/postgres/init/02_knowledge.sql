-- ============================================================
-- Phase 3 — Knowledge Service schema
-- Tracks ingested documents and their chunk metadata so the
-- application database stays in sync with the FAISS index.
-- ============================================================

-- ── Documents table ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS documents (
    id              TEXT PRIMARY KEY,          -- caller-assigned stable ID
    tenant_id       UUID NOT NULL,
    title           VARCHAR(512) NOT NULL,
    content_hash    TEXT NOT NULL,             -- SHA-256 of original content
    chunk_count     INTEGER NOT NULL DEFAULT 0,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_documents_tenant_id  ON documents (tenant_id);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents (created_at DESC);

-- ── Auto-update updated_at ────────────────────────────────────
DROP TRIGGER IF EXISTS trg_documents_updated_at ON documents;
CREATE TRIGGER trg_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();   -- reuses function from 01_schema.sql

-- ── Row-Level Security ────────────────────────────────────────
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS documents_local_dev_all ON documents;
CREATE POLICY documents_local_dev_all
    ON documents
    FOR ALL
    TO postgres
    USING (true)
    WITH CHECK (true);
