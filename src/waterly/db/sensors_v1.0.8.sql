-- Sensor inventory. Legacy zone address columns remain for historical compatibility.
BEGIN;
CREATE TABLE sensor (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL CHECK(length(trim(name)) BETWEEN 1 AND 80),
    type TEXT NOT NULL CHECK(type IN ('SEN0604', 'SEN0605', 'SEN0438')),
    address INTEGER NOT NULL UNIQUE CHECK(address BETWEEN 1 AND 247),
    zone_id INTEGER REFERENCES zone(id),
    enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0, 1)),
    revision INTEGER NOT NULL DEFAULT 1,
    applied_revision INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'untested',
    last_seen TEXT,
    last_error TEXT,
    last_reading TEXT,
    test_pending INTEGER NOT NULL DEFAULT 0,
    tested_at TEXT,
    test_success INTEGER,
    test_error TEXT,
    UNIQUE(zone_id, type)
);
INSERT INTO sensor(name, type, address, zone_id)
SELECT name || ' soil', 'SEN0604', rh_sensor_address, id FROM zone
WHERE relay_address IS NOT NULL AND rh_sensor_address IS NOT NULL;
INSERT INTO sensor(name, type, address, zone_id)
SELECT name || ' NPK', 'SEN0605', npk_sensor_address, id FROM zone
WHERE relay_address IS NOT NULL AND npk_sensor_address IS NOT NULL;
INSERT INTO sensor(name, type, address, zone_id)
SELECT name || ' air', 'SEN0438', rh_sensor_address, id FROM zone
WHERE name = 'ENV' AND rh_sensor_address IS NOT NULL;
COMMIT;
