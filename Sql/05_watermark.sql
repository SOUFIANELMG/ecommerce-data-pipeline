-- WATERMARK TABLE
CREATE TABLE IF NOT EXISTS analytics.etl_watermark (
    pipeline_name VARCHAR(100) PRIMARY KEY,
    last_successful_at TIMESTAMPTZ NOT NULL
);


-- Initial watermark

INSERT INTO analytics.etl_watermark (
    pipeline_name,
    last_successful_at
)
VALUES (
    'ecommerce_incremental',
    '1970-01-01 00:00:00+00'
)
ON CONFLICT (pipeline_name) DO NOTHING;

