/*
 * MIT License
 *
 * Copyright (c) 2025 by Dan Luca. All rights reserved.
 *
 */

-- Zone descriptions
update zone set description='Zone 1 (right row, near house)' where name = 'Z1';
update zone set description='Zone 2 (middle row)' where name = 'Z2';
update zone set description='Zone 3 (left row, sports court)' where name = 'Z3';
update zone set description='Raspberry Pi' where name = 'RPI';

-- 1) Watering assessment: captures the decision context and planned timing (no zone)
CREATE TABLE IF NOT EXISTS watering_assessment (
  id               INTEGER PRIMARY KEY,
  start_ts_utc     INTEGER NOT NULL,           -- scheduled/decision start (UTC epoch ms to match existing conventions)
  tz               TEXT,                       -- timezone identifier for human display
  enabled          INTEGER NOT NULL DEFAULT 0, -- 1 = enabled, 0 = disabled
  reason_json      TEXT NOT NULL CHECK (json_valid(reason_json)),  -- JSON inputs/decision rationale
  created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_wassm_start ON watering_assessment(start_ts_utc);

-- 2) Watering record: per-zone execution outcome linked to an assessment
CREATE TABLE IF NOT EXISTS watering_record (
  id               INTEGER PRIMARY KEY,
  assessment_id    INTEGER NOT NULL,
  zone_id          INTEGER NOT NULL,
  executed         INTEGER NOT NULL DEFAULT 0,    -- 1 = executed, 0 = skipped for this zone
  duration_sec     INTEGER NOT NULL,              -- duration of watering in seconds
  humidity_start   REAL,                          -- % RH (soil moisture proxy)
  humidity_end     REAL,                          -- % RH (soil moisture proxy)
  water_amount     REAL,                          -- amount of water dispensed for this zone
  water_unit       TEXT DEFAULT 'L',              -- e.g., 'L' liters or 'gal'
  created_at       TEXT NOT NULL DEFAULT (datetime('now')),

  CONSTRAINT fk_wr_assessment FOREIGN KEY (assessment_id) REFERENCES watering_assessment(id) ON DELETE CASCADE,
  CONSTRAINT fk_wr_zone       FOREIGN KEY (zone_id)       REFERENCES zone(id)                ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_wrecord_zone ON watering_record(zone_id);
CREATE INDEX IF NOT EXISTS idx_wrecord_assessment ON watering_record(assessment_id);
CREATE INDEX IF NOT EXISTS idx_wrecord_executed ON watering_record(executed);

-- Provide an aggregated view approximating the overall water logs
-- Note: humidity/water fields come from the per-zone record; reason_json & timing from the assessment
DROP VIEW IF EXISTS water_log_view;
CREATE VIEW water_log_view AS
SELECT wr.id                 AS id,
       wr.zone_id            AS zone_id,
       wa.start_ts_utc       AS start_ts_utc,
       wa.tz                 AS tz,
       wa.duration_sec       AS duration_sec,
       wr.executed           AS executed,
       wa.reason_json        AS reason_json,
       wr.humidity_start     AS humidity_start,
       wr.humidity_end       AS humidity_end,
       wr.water_amount       AS water_amount,
       wr.water_unit         AS water_unit,
       wr.created_at         AS created_at
  FROM watering_record wr
  JOIN watering_assessment wa ON wa.id = wr.assessment_id;















-- Water log: records the watering events for each zone
-- Requirements:
--  - duration of watering
--  - reason for watering (JSON)
--  - whether executed or skipped
--  - humidity at the beginning and end of watering interval
--  - amount of water used
CREATE TABLE IF NOT EXISTS water_log (
  id                 INTEGER PRIMARY KEY,
  zone_id            INTEGER NOT NULL,

  -- Planned/actual timing
  start_ts_utc       INTEGER NOT NULL,      -- scheduled or actual start (UTC epoch seconds)
  tz                 TEXT,                  -- timezone identifier used when scheduling/executing (optional)
  duration_sec       INTEGER NOT NULL,      -- watering duration in seconds (planned or actual)

  -- Execution status
  executed           INTEGER NOT NULL DEFAULT 0,  -- 1 = executed, 0 = skipped
  reason_json        TEXT NOT NULL CHECK (json_valid(reason_json)), -- JSON blob with decision inputs

  -- Environment measurements
  humidity_start     REAL,                   -- % RH (soil moisture proxy)
  humidity_end       REAL,                   -- % RH (soil moisture proxy)

  -- Water usage
  water_amount       REAL,                   -- numeric amount of water dispensed
  water_unit         TEXT DEFAULT 'L',       -- e.g., 'L' liters, 'gal'

  created_at         TEXT NOT NULL DEFAULT (datetime('now')),

  FOREIGN KEY (zone_id) REFERENCES zone(id) ON DELETE CASCADE
);

-- Helpful indexes
CREATE INDEX IF NOT EXISTS idx_water_log_zone_ts ON water_log(zone_id, start_ts_utc);
CREATE INDEX IF NOT EXISTS idx_water_log_executed ON water_log(executed);
