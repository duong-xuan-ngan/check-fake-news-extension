CREATE TABLE IF NOT EXISTS sources (
    domain            VARCHAR PRIMARY KEY,
    credibility_score FLOAT   NOT NULL,
    category          VARCHAR NOT NULL,
    last_updated      DATE
);

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