-- =====================================================================
-- AEO Audit Engine :: relational backbone (PostgreSQL 16 + pgvector)
-- Idempotent. Executed by docker-entrypoint on first boot and again by
-- the NLP worker at startup, so local (non-Docker) runs work too.
-- =====================================================================
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS institutions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug        VARCHAR(80) UNIQUE NOT NULL,
    name        VARCHAR(255) NOT NULL,
    domain      VARCHAR(255),
    homepage    TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- SPEC: entity_nodes (id, entity_name, namespace_type Retail / Institutional)
CREATE TABLE IF NOT EXISTS entity_nodes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_name     VARCHAR(255) NOT NULL,
    namespace_type  VARCHAR(50)  NOT NULL,               -- Retail / Institutional / Brand
    institution_id  UUID REFERENCES institutions(id) ON DELETE CASCADE,
    slug            VARCHAR(120) NOT NULL,
    entity_kind     VARCHAR(50)  NOT NULL DEFAULT 'product',  -- product / division / brand
    aliases         TEXT[]       NOT NULL DEFAULT '{}',
    descriptors     JSONB        NOT NULL DEFAULT '{}'::jsonb, -- audience, support model ...
    replaces_entity UUID REFERENCES entity_nodes(id),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    UNIQUE (institution_id, slug)
);

-- SPEC: temporal_embeddings (id, entity_id, embedding vector(768), valid_from, valid_to)
CREATE TABLE IF NOT EXISTS temporal_embeddings (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id     UUID REFERENCES entity_nodes(id) ON DELETE CASCADE,
    embedding     vector(768) NOT NULL,
    valid_from    TIMESTAMPTZ NOT NULL,
    valid_to      TIMESTAMPTZ,
    source_type   VARCHAR(40) NOT NULL,      -- institutional_filing / institutional_web / press / retail_forum
    source_url    TEXT,
    namespace_type VARCHAR(50),
    content       TEXT NOT NULL,
    content_hash  VARCHAR(64) NOT NULL,
    authority     REAL NOT NULL DEFAULT 0.5,
    link_count    INTEGER NOT NULL DEFAULT 0,
    sentiment     JSONB,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_te_entity      ON temporal_embeddings(entity_id, valid_from);
CREATE INDEX IF NOT EXISTS idx_te_hash        ON temporal_embeddings(content_hash);
CREATE INDEX IF NOT EXISTS idx_te_embedding   ON temporal_embeddings USING hnsw (embedding vector_cosine_ops);

-- Atomic, attributed numeric claims extracted from text (nodes of the temporal graph)
CREATE TABLE IF NOT EXISTS fact_claims (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID NOT NULL REFERENCES entity_nodes(id) ON DELETE CASCADE,
    embedding_id    UUID REFERENCES temporal_embeddings(id) ON DELETE SET NULL,
    attribute       VARCHAR(80) NOT NULL,
    value_num       DOUBLE PRECISION,
    value_text      TEXT,
    unit            VARCHAR(20),
    source_type     VARCHAR(40) NOT NULL,
    source_url      TEXT,
    observed_at     TIMESTAMPTZ NOT NULL,
    valid_from      TIMESTAMPTZ NOT NULL,
    valid_to        TIMESTAMPTZ,
    link_count      INTEGER NOT NULL DEFAULT 0,
    authority       REAL NOT NULL DEFAULT 0.5,
    confidence      REAL NOT NULL DEFAULT 0.5,
    is_ground_truth BOOLEAN NOT NULL DEFAULT false,
    status          VARCHAR(20) NOT NULL DEFAULT 'active',   -- active / superseded / contested
    supersedes      UUID REFERENCES fact_claims(id),
    evidence        TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_fc_entity_attr ON fact_claims(entity_id, attribute, observed_at);

CREATE TABLE IF NOT EXISTS graph_edges (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    src_id      UUID NOT NULL,
    dst_id      UUID NOT NULL,
    relation    VARCHAR(40) NOT NULL,          -- SUPERSEDES / CONTRADICTS / SUPPORTS / PART_OF
    weight      REAL NOT NULL DEFAULT 1.0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_edges_src ON graph_edges(src_id);
CREATE INDEX IF NOT EXISTS idx_edges_dst ON graph_edges(dst_id);

-- SPEC: corroboration_logs, retail sentiment vs institutional ground truth
CREATE TABLE IF NOT EXISTS corroboration_logs (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id              UUID NOT NULL REFERENCES entity_nodes(id) ON DELETE CASCADE,
    attribute              VARCHAR(80) NOT NULL,
    computed_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    ground_truth_value     DOUBLE PRECISION,
    ground_truth_claim     UUID,
    naive_gt_share         REAL,
    temporal_gt_share      REAL,
    corroboration_deficit  REAL,
    stale_claims           INTEGER,
    retail_sentiment       REAL,
    details                JSONB
);

CREATE TABLE IF NOT EXISTS pages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    institution_id  UUID REFERENCES institutions(id) ON DELETE CASCADE,
    url             TEXT UNIQUE NOT NULL,
    title           TEXT,
    namespace_type  VARCHAR(50),
    is_landing      BOOLEAN NOT NULL DEFAULT false,
    static_text     TEXT,
    rendered_text   TEXT,
    embedding       vector(768),
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS scrape_logs (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    institution_id   UUID REFERENCES institutions(id) ON DELETE CASCADE,
    url              TEXT NOT NULL,
    fetched_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    render_mode      VARCHAR(30),
    static_tokens    INTEGER,
    rendered_tokens  INTEGER,
    static_facts     INTEGER,
    rendered_facts   INTEGER,
    extraction_loss  REAL,
    details          JSONB
);

CREATE TABLE IF NOT EXISTS severance_runs (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    institution_id   UUID REFERENCES institutions(id) ON DELETE CASCADE,
    query            TEXT NOT NULL,
    landing_url      TEXT,
    cosine_distance  REAL,
    severance_score  REAL,
    best_match_url   TEXT,
    hydrate          BOOLEAN,
    payload          JSONB,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dilution_runs (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    institution_id   UUID REFERENCES institutions(id) ON DELETE CASCADE,
    dilution_index   REAL,
    attribute_bleed  REAL,
    details          JSONB,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_log (
    id       BIGSERIAL PRIMARY KEY,
    ts       TIMESTAMPTZ NOT NULL DEFAULT now(),
    level    VARCHAR(10) NOT NULL,
    source   VARCHAR(40) NOT NULL,
    message  TEXT NOT NULL,
    data     JSONB
);

-- ---- orchestration layer (owned by the Spring Boot service) ----
CREATE TABLE IF NOT EXISTS scrape_schedules (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    institution_slug VARCHAR(80) NOT NULL,
    url              TEXT NOT NULL,
    interval_minutes INTEGER NOT NULL DEFAULT 60,
    enabled          BOOLEAN NOT NULL DEFAULT true,
    last_run_at      TIMESTAMPTZ,
    entity_slug      VARCHAR(120),
    namespace_type   VARCHAR(50),
    UNIQUE (institution_slug, url)
);

CREATE TABLE IF NOT EXISTS orchestration_jobs (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kind         VARCHAR(40) NOT NULL,
    status       VARCHAR(20) NOT NULL,
    request      JSONB,
    result       JSONB,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at  TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS webhook_events (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source       VARCHAR(80) NOT NULL,
    signature_ok BOOLEAN NOT NULL,
    body         JSONB,
    received_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
