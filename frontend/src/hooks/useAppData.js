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
    const minutes17 = 17 * 60 * 1000;
    const id = setInterval(() => {
      fetchSensors().then(setSensorData).catch(() => {});
    }, minutes17);
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
