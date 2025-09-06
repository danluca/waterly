import React from 'react';
import { Card, CardContent, Typography } from '@mui/material';
import { Line } from 'react-chartjs-2';

// Assume props: { groupLabel, sensors: [{name, times, values, color}] }
function GroupedSensorChart({ groupLabel, sensors }) {
  const allLabels = sensors[0]?.times || [];
  const datasets = sensors.map((sensor, idx) => ({
    label: sensor.name,
    data: sensor.values,
    borderColor: sensor.color || `hsl(${idx * 80},70%,50%)`,
    fill: false,
    pointRadius: 2
  }));

  const data = { labels: allLabels, datasets };

  const options = {
    responsive: true,
    plugins: {
      legend: { display: true },
      zoom: {
        pan: { enabled: true, mode: 'x' },
        zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: 'x' }
      }
    },
    scales: {
      x: {
        type: 'time',
        time: { unit: 'hour', stepSize: 1, displayFormats: { hour: 'HH:mm' } },
        grid: { color: '#eee' }
      },
      y: { grid: { color: '#eee' } }
    }
  };

  return (
    <Card variant="outlined" sx={{ marginBottom: 2 }}>
      <CardContent>
        <Typography variant="h6">{groupLabel}</Typography>
        <Line data={data} options={options} />
      </CardContent>
    </Card>
  );
}

export default GroupedSensorChart;
