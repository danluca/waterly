/*
 * MIT License
 *
 * Copyright (c) 2025 by Dan Luca. All rights reserved.
 *
 */

-- Migration history table (Flyway-like)
CREATE TABLE IF NOT EXISTS migration_history (
  installed_rank      INTEGER PRIMARY KEY,                 -- rowid-backed; installation order
  version             TEXT,                                -- e.g., '1.2.0'; may be NULL for repeatable
  description         TEXT NOT NULL,                       -- short human description
  checksum            TEXT,                                -- SHA-256 checksum of the migration source
  installed_on        TEXT NOT NULL DEFAULT (datetime('now')) -- UTC time of application
);

-- Uniqueness constraints:
--  - version: one row per version (NULL allowed for repeatables)
--  - script: prevents re-applying the same script name
CREATE UNIQUE INDEX IF NOT EXISTS ux_migration_history_version ON migration_history(version);
CREATE UNIQUE INDEX IF NOT EXISTS ux_migration_history_checksum  ON migration_history(checksum);

-- Helpful indexes
CREATE INDEX IF NOT EXISTS idx_migration_history_installed_on ON migration_history(installed_on);        -- Zones: human-friendly name + hardware addresses (nullable if not present)

-- Zones: human-friendly name + hardware addresses (nullable if not present)
CREATE TABLE zone (
  id                   INTEGER PRIMARY KEY,
  name                 TEXT NOT NULL UNIQUE,            -- e.g., "Z1", "Z2"
  description          TEXT,
  rh_sensor_address    INTEGER,                         -- e.g., RS485/Modbus address
  npk_sensor_address   INTEGER,                         -- e.g., RS485/Modbus address
  relay_address        INTEGER,                         -- GPIO terminal controlling the relay
  created_at           TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at           TEXT
);

-- Maintain updated_at automatically
CREATE TRIGGER trg_zone_updated_at
AFTER UPDATE ON zone
FOR EACH ROW
BEGIN
  UPDATE zone SET updated_at = datetime('now') WHERE id = NEW.id;
END;

-- Measurements: value readings tied to a zone and a metric name/unit
-- Timestamp is stored as Unix epoch seconds (UTC) for efficient range queries.
-- tz stores the timezone name used when the reading was taken (e.g., "America/Chicago")
CREATE TABLE measurement (
  id          INTEGER PRIMARY KEY,
  zone_id     INTEGER NOT NULL,
  name        TEXT NOT NULL,            -- metric name (e.g., "humidity", "temp", "npk_n")
  unit        TEXT NOT NULL,            -- unit string (e.g., "%", "C", "ppm")
  ts_utc      INTEGER NOT NULL,         -- UTC epoch seconds
  tz          TEXT,                     -- timezone identifier used when sampling (optional)
  reading     REAL NOT NULL,            -- numeric reading
  created_at  TEXT NOT NULL DEFAULT (datetime('now')),

  FOREIGN KEY (zone_id) REFERENCES zone(id) ON DELETE CASCADE,

  -- Prevent duplicate samples for the same metric at the same instant
  UNIQUE (zone_id, name, ts_utc));

-- Helpful indexes for common queries
CREATE INDEX idx_measurement_zone_ts ON measurement (zone_id, ts_utc);
CREATE INDEX idx_measurement_zone_name_ts ON measurement (zone_id, name, ts_utc);
CREATE INDEX idx_measurement_name_ts ON measurement (name, ts_utc);

-- Config: one row per setting (type = key from Settings enum)
-- Value is JSON (validated when JSON1 extension is available).
CREATE TABLE config (
  type   TEXT PRIMARY KEY,                        -- must match a Settings key (e.g., "LOCAL_TIMEZONE")
  value  TEXT NOT NULL CHECK (json_valid(value))  -- serialized JSON value
) WITHOUT ROWID;

-- Weather: hourly forecasts with explicit units per field
-- collected_at_utc: when this forecast set was fetched
-- forecast_ts_utc: the forecast hour timestamp (UTC)
-- precipitation_probability: store as 0..1 (fraction)
CREATE TABLE weather (
  id                           INTEGER PRIMARY KEY,
  collected_at_utc             INTEGER NOT NULL,  -- UTC epoch seconds (fetch time)
  forecast_ts_utc              INTEGER NOT NULL,  -- UTC epoch seconds (hourly forecast time)
  tz                           TEXT,              -- source timezone identifier
  tag                          TEXT,              -- source hourly time identifier

  temperature_2m               REAL,              -- air temperature at 2m
  temperature_unit             TEXT,              -- e.g., "celsius" or "fahrenheit"

  precipitation_probability    REAL,              -- 0..100 %
  precipitation                REAL,              -- precipitation amount for the hour
  precipitation_unit           TEXT,              -- e.g., "mm" or "in"

  soil_moisture_1_to_3cm       REAL,              -- m³/m³
  moisture_unit                TEXT,              -- e.g., "m³/m³" or "% m³/m³" label

  surface_pressure             REAL,              -- mean sea level or surface pressure, depending on source
  pressure_unit                TEXT,              -- e.g., "hPa" or "inHg"

  created_at                   TEXT NOT NULL DEFAULT (datetime('now')),

  -- Avoid duplicate entries for the same forecast hour
  UNIQUE (forecast_ts_utc)
);

-- Helpful indexes for time-based queries
CREATE INDEX idx_weather_forecast_ts ON weather (forecast_ts_utc);
CREATE INDEX idx_weather_collected_ts ON weather (collected_at_utc);

-- Optional convenience views

-- Latest measurement per zone and metric
CREATE VIEW v_latest_measurement AS
SELECT m.*
FROM measurement m
JOIN (
  SELECT zone_id, name, MAX(ts_utc) AS max_ts
  FROM measurement
  GROUP BY zone_id, name
) t
ON t.zone_id = m.zone_id AND t.name = m.name AND t.max_ts = m.ts_utc;

-- Latest measurement per zone for all metrics as a wide-ish list
-- (useful for dashboards that need current values by zone)
CREATE VIEW v_latest_by_zone AS
SELECT z.id AS zone_id,
       z.name AS zone_name,
       m.name AS metric_name,
       m.unit,
       m.reading,
       m.ts_utc,
       m.tz
FROM zone z
LEFT JOIN v_latest_measurement m
  ON m.zone_id = z.id;

-- Optional: latest forecast per hour (handy when you may re-fetch)
CREATE VIEW v_latest_weather AS
SELECT w.*
FROM weather w
JOIN (
  SELECT forecast_ts_utc, MAX(collected_at_utc) AS max_collected
  FROM weather
  GROUP BY forecast_ts_utc
) t
ON t.forecast_ts_utc = w.forecast_ts_utc AND t.max_collected = w.collected_at_utc;
