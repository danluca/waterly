-- Purges are maintenance operations and never contribute to watering measurements.
CREATE TABLE purge_log (
    id INTEGER PRIMARY KEY,
    zone TEXT NOT NULL,
    started_at TEXT NOT NULL,
    requested_seconds INTEGER NOT NULL,
    ended_at TEXT,
    duration_seconds REAL,
    outcome TEXT NOT NULL
);
