/*
 * MIT License
 *
 * Copyright (c) 2025 by Dan Luca. All rights reserved.
 *
 */

DROP TABLE IF EXISTS water_log;
DROP VIEW IF EXISTS water_log_view;
-- Provide an aggregated view approximating the overall water logs
-- Note: humidity/water, timing fields come from the per-zone record; reason_json & assessment timing from the assessment
CREATE VIEW water_log_view AS
SELECT wr.id                 AS id,
       wr.zone_id            AS zone_id,
       wr.assessment_id      AS assessment_id,
       wa.start_ts_utc       AS assess_ts_utc,
       wa.tz                 AS assess_tz,
       wr.start_ts_utc       AS start_ts_utc,
       wr.start_ts_tz        AS start_tz,
       wr.duration_sec       AS duration_sec,
       wr.executed           AS executed,
       wa.reason_json        AS reason_json,
       wr.humidity_start     AS humidity_start,
       wr.humidity_end       AS humidity_end,
       wr.water_amount       AS water_amount,
       wr.water_unit         AS water_unit,
       wr.created_at         AS created_at
  FROM watering_record wr
  JOIN watering_assessment wa ON wa.id = wr.assessment_id;
