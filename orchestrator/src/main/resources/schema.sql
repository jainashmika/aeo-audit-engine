-- Orchestration tables (also created by db/init.sql; repeated so the service can boot standalone)
CREATE TABLE IF NOT EXISTS scrape_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    institution_slug VARCHAR(80) NOT NULL,
    url TEXT NOT NULL,
    interval_minutes INTEGER NOT NULL DEFAULT 60,
    enabled BOOLEAN NOT NULL DEFAULT true,
    last_run_at TIMESTAMPTZ,
    UNIQUE (institution_slug, url)
);
CREATE TABLE IF NOT EXISTS orchestration_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kind VARCHAR(40) NOT NULL,
    status VARCHAR(20) NOT NULL,
    request JSONB,
    result JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS webhook_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source VARCHAR(80) NOT NULL,
    signature_ok BOOLEAN NOT NULL,
    body JSONB,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE scrape_schedules ADD COLUMN IF NOT EXISTS entity_slug VARCHAR(120);
ALTER TABLE scrape_schedules ADD COLUMN IF NOT EXISTS namespace_type VARCHAR(50);
