/*
 * MIT License
 *
 * Copyright (c) 2025 by Dan Luca. All rights reserved.
 *
 */
import axios from 'axios';

const BASE_URL = '/api';

export async function fetchManifest() {
  // returns build manifest
  const response = await axios.get(`${BASE_URL}/manifest`);
  return response.data;
}
