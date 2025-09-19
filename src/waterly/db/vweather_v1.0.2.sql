/*
 * MIT License
 *
 * Copyright (c) 2025 by Dan Luca. All rights reserved.
 *
 */

drop view v_latest_weather;

-- View: weather window around "now" (previous 12h and next 12h), using UTC epoch seconds
-- Uses v_latest_weather to ensure a single row per forecast hour
CREATE VIEW v_weather_12h_window AS
WITH now_epoch AS (SELECT CAST(strftime('%s','now') AS INTEGER) * 1000 AS now_ms )
SELECT w.*
FROM weather w, now_epoch n
WHERE w.forecast_ts_utc BETWEEN (n.now_ms - 12*3600*1000) AND (n.now_ms + 12*3600*1000)
ORDER BY w.forecast_ts_utc;