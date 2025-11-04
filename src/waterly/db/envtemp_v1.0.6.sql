/*
 * MIT License
 *
 * Copyright (c) 2025 by Dan Luca. All rights reserved.
 *
 */

-- Migration v1.0.6
-- Add environment zone with air temperature sensor
insert or replace into zone(name, description, rh_sensor_address, npk_sensor_address, relay_address)
    values('ENV', 'Environment', 0x30, null, null);
