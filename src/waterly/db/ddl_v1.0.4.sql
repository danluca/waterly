/*
 * MIT License
 *
 * Copyright (c) 2025 by Dan Luca. All rights reserved.
 *
 */

-- Migration v1.0.4
-- Add execution start timestamp and timezone to watering_record

-- Add new columns to watering_record (introduced in v1.0.3)
-- SQLite prior to 3.35 does not support IF NOT EXISTS for ADD COLUMN; repeated application should be avoided by migration runner
ALTER TABLE watering_record ADD COLUMN start_ts_utc INTEGER NOT NULL DEFAULT 0;     -- UTC epoch ms for execution start
ALTER TABLE watering_record ADD COLUMN start_ts_tz  TEXT;                           -- timezone identifier at execution start

-- Helpful index for time-based queries on the new column
CREATE INDEX IF NOT EXISTS idx_wrecord_start ON watering_record(start_ts_utc);
