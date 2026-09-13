CREATE TABLE measurement (
    measurement_id VARCHAR(120) PRIMARY KEY,
    sensor_id VARCHAR(120) NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL,
    raw_value NUMERIC(24, 9) NOT NULL,
    calibrated_value NUMERIC(24, 9) NOT NULL,
    stored_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX measurement_sensor_time_idx ON measurement (sensor_id, captured_at);
