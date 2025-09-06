import axios from 'axios';

const BASE_URL = '/api';

export async function fetchSensors() {
  // returns: [{name, times, values, latestValue, group}]
  const response = await axios.get(`${BASE_URL}/sensors.json`);
  return response.data;
}

export async function fetchGroupedSensors() {
  // returns grouped data if API supports
  const response = await axios.get(`${BASE_URL}/sensors.json`);
  return response.data.measurements;
}
