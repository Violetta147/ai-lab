-- ================================================================
-- Schema khởi tạo cho bảng detections
-- Pipeline status flow: NEW → INFERRED → IN_CVAT → LABELED → TRAINED
-- ================================================================

CREATE TABLE IF NOT EXISTS detections (
    id              SERIAL PRIMARY KEY,
    camera_id       VARCHAR(50)  NOT NULL,
    image_url       TEXT         NOT NULL,
    "timestamp"     TIMESTAMP    NOT NULL,
    trigger_reason  TEXT,
    status          VARCHAR(20)  NOT NULL DEFAULT 'NEW'
                    CHECK (status IN ('NEW', 'INFERRED', 'IN_CVAT', 'LABELED', 'TRAINED')),
    cvat_task_id    INTEGER,
    edge_predictions JSONB,
    created_at      TIMESTAMP    NOT NULL DEFAULT NOW()
);

-- Index cho query theo status (dùng nhiều nhất trong pipeline)
CREATE INDEX IF NOT EXISTS idx_detections_status
    ON detections(status);

-- Index cho query theo cvat_task_id (dùng trong export_labeled_data_task)
CREATE INDEX IF NOT EXISTS idx_detections_cvat_task_id
    ON detections(cvat_task_id)
    WHERE cvat_task_id IS NOT NULL;

-- Index cho query sắp xếp theo timestamp (dùng trong get_records_by_status)
CREATE INDEX IF NOT EXISTS idx_detections_timestamp
    ON detections("timestamp");

-- Index cho query theo camera_id (phục vụ analytics sau này)
CREATE INDEX IF NOT EXISTS idx_detections_camera_id
    ON detections(camera_id);
