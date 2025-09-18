import axios from 'axios';

const BASE_URL = '/api';

export async function fetchSensors() {
  // returns: [{name, times, values, latestValue, group}]
  const response = await axios.get(`${BASE_URL}/latest/sensors`);
  return response.data;
}
