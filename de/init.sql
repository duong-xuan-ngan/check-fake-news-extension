CREATE TABLE IF NOT EXISTS sources (
    domain            VARCHAR PRIMARY KEY,
    credibility_score FLOAT   NOT NULL,
    category          VARCHAR NOT NULL,
    country           VARCHAR NOT NULL DEFAULT 'unknown',
    rating_source     VARCHAR NOT NULL DEFAULT 'manual',
    source_count      INTEGER,
    source_version    VARCHAR,
    last_updated      DATE
);

-- CREATE TABLE IF NOT EXISTS does not modify an existing table. This keeps
-- databases created by older versions compatible with the current schema.
ALTER TABLE sources
    ADD COLUMN IF NOT EXISTS country VARCHAR NOT NULL DEFAULT 'unknown';

ALTER TABLE sources
    ADD COLUMN IF NOT EXISTS rating_source VARCHAR NOT NULL DEFAULT 'manual';

ALTER TABLE sources
    ADD COLUMN IF NOT EXISTS source_count INTEGER;

ALTER TABLE sources
    ADD COLUMN IF NOT EXISTS source_version VARCHAR;

CREATE TABLE IF NOT EXISTS pipeline_logs (
    id                VARCHAR PRIMARY KEY,
    input_hash        VARCHAR NOT NULL,
    timestamp         VARCHAR NOT NULL,
    steps_completed   TEXT,
    verdict           VARCHAR,
    error_stage       VARCHAR,
    error_message     TEXT,
    response_time_ms  INTEGER
);

-- Domains returned by search that are not present in the curated `sources`
-- table. This is a review queue: discovering a domain must never imply that it
-- is either credible or unreliable.
CREATE TABLE IF NOT EXISTS source_candidates (
    domain             VARCHAR PRIMARY KEY,
    sample_url         TEXT NOT NULL,
    discovery_source   VARCHAR NOT NULL DEFAULT 'serper_google',
    review_status      VARCHAR NOT NULL DEFAULT 'pending'
                       CHECK (review_status IN ('pending', 'approved', 'rejected')),
    discovery_count    BIGINT NOT NULL DEFAULT 1 CHECK (discovery_count > 0),
    first_seen_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS source_candidates_review_queue_idx
    ON source_candidates (review_status, last_seen_at DESC);
