/*
 * MIT License
 *
 * Copyright (c) 2025 by Dan Luca. All rights reserved.
 *
 */

import {useEffect, useState} from 'react';
import {fetchSensors} from '../api/sensors';
import {fetchManifest} from '../api/manifest';

export default function useAppData() {
  const [sensorData, setSensorData] = useState([]);
  const [manifest, setManifest] = useState(null);

  useEffect(() => {
    fetchSensors().then(setSensorData);
  }, []);

  useEffect(() => {
    fetchManifest().then(setManifest);
  }, []);

  useEffect(() => {
    // Poll at 17 min: faster than the 10-min sensor read interval so fresh data lands quickly,
    // but slow enough to avoid hammering the Pi between reads.
    const SENSOR_POLL_INTERVAL_MS = 17 * 60 * 1000;
    const id = setInterval(() => {
      fetchSensors().then(setSensorData).catch(() => {});
    }, SENSOR_POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, []);

  const refreshSensors = async () => {
    try {
      const data = await fetchSensors();
      setSensorData(data);
    } catch (e) {
      // ignore
    }
  };

  return { sensorData, manifest, setSensorData, setManifest, refreshSensors };
}
