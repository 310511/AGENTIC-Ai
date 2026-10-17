-- ============================================================
-- AI Agent Platform — initial PostgreSQL schema
-- Applied automatically when the local postgres container
-- starts for the first time.
--
-- In production, use Supabase migrations or Alembic.
-- ============================================================

-- ── Extensions ────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── Enum types ────────────────────────────────────────────────
DO $$ BEGIN
    CREATE TYPE task_priority AS ENUM ('low', 'normal', 'high');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE task_status AS ENUM (
        'pending',
        'queued',
        'in_progress',
        'awaiting_approval',
        'completed',
        'failed',
        'cancelled'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ── Tasks table ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tasks (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL,
    created_by      UUID NOT NULL,
    title           VARCHAR(256) NOT NULL,
    description     TEXT NOT NULL,
    priority        task_priority NOT NULL DEFAULT 'normal',
    status          task_status NOT NULL DEFAULT 'pending',
    result          JSONB,
    error_message   TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);

-- ── Indexes ───────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_tasks_tenant_id   ON tasks (tenant_id);
CREATE INDEX IF NOT EXISTS idx_tasks_created_by  ON tasks (created_by);
CREATE INDEX IF NOT EXISTS idx_tasks_status      ON tasks (status);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at  ON tasks (created_at DESC);

-- ── Auto-update updated_at ────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_tasks_updated_at ON tasks;
CREATE TRIGGER trg_tasks_updated_at
    BEFORE UPDATE ON tasks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ── Row-Level Security (RLS) ──────────────────────────────────
-- Enable RLS. In production (Supabase), define policies that
-- restrict rows to the authenticated user's tenant_id using
-- the current_setting('request.jwt.claims')::json->>'tenant_id'
-- pattern. For local dev, RLS is enabled but no restrictive
-- policy is attached so the dev user can read all rows.
ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;

-- Permissive local-dev policy (PostgreSQL user = 'postgres').
-- Replace with Supabase Auth policies in production.
DROP POLICY IF EXISTS tasks_local_dev_all ON tasks;
CREATE POLICY tasks_local_dev_all
    ON tasks
    FOR ALL
    TO postgres
    USING (true)
    WITH CHECK (true);
