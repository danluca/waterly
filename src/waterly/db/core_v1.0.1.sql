/*
 * MIT License
 *
 * Copyright (c) 2025 by Dan Luca. All rights reserved.
 *
 */
-- Zones
insert or replace into zone(name, description, rh_sensor_address, npk_sensor_address, relay_address)
    values('Z1', 'Zone 1', 0x0A, null, 19);
insert or replace into zone(name, description, rh_sensor_address, npk_sensor_address, relay_address)
    values('Z2', 'Zone 2', 0x0B, 0x20, 16);
insert or replace into zone(name, description, rh_sensor_address, npk_sensor_address, relay_address)
    values('Z3', 'Zone 3', 0x0C, null, 20);
insert or replace into zone(name, description, rh_sensor_address, npk_sensor_address, relay_address)
    values('RPI', 'Raspberry PI Zero 2W', null, null, null);

-- Config
insert or replace into config(type, value) values('HUMIDITY_TARGET_PERCENT', '{"Z1": 75.0,"Z2": 70.0,"Z3": 70.0}');
insert or replace into config(type, value) values('WATERING_START_TIME', '{"value": "20:30"}');
insert or replace into config(type, value) values('WATERING_MAX_MINUTES_PER_ZONE', '{"value": 10}');
insert or replace into config(type, value) values('LAST_WATERING_DATE', '{"value": "2025-09-11"}');
insert or replace into config(type, value) values('RAIN_CANCEL_PROBABILITY_THRESHOLD', '{"value": 50}');
insert or replace into config(type, value) values('UNITS', '{"value": "imperial"}');
insert or replace into config(type, value) values('WEATHER_CHECK_INTERVAL_SECONDS', '{"value": 21600}');
insert or replace into config(type, value) values('SENSOR_READ_INTERVAL_SECONDS', '{"value": 900}');
insert or replace into config(type, value) values('TREND_MAX_SAMPLES', '{"value": 36000}');
insert or replace into config(type, value) values('LOCAL_TIMEZONE', '{"value": "America/Chicago"}');
insert or replace into config(type, value) values('LOCATION', '{"longitude": -93.45025,"latitude": 45.031667}');
insert or replace into config(type, value) values('GARDENING_SEASON', '{"start": "03-31","stop": "10-31"}');
insert or replace into config(type, value) values('WEATHER_LAST_CHECK_TIMESTAMP', '{"__type__": "datetime", "iso": "2025-09-12T10:42:40.447833-05:00","tz": "America/Chicago"}');
insert or replace into config(type, value) values('WEATHER_CHECK_PRE_WATERING_SECONDS', '{"value": 1800}');
insert or replace into config(type, value) values('MINIMUM_SENSOR_HUMIDITY_PERCENT', '{"Z1": 30.0,"Z2": 30.0,"Z3": 30.0}');




