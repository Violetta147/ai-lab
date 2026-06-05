-- Initialize tables for traffic_db
-- This script is automatically executed by the postgres docker container on first boot.

CREATE TABLE IF NOT EXISTS detections (
    id SERIAL PRIMARY KEY,
    camera_id VARCHAR(50) NOT NULL,
    image_url TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    trigger_reason VARCHAR(100),
    status VARCHAR(20) DEFAULT 'NEW',
    cvat_task_id INT,
    edge_predictions JSONB
);

-- Optional: Create an index for faster queries by status and timestamp
CREATE INDEX IF NOT EXISTS idx_detections_status_time ON detections (status, timestamp);
