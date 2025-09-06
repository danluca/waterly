import React from 'react';
import { Card, CardContent, Typography } from '@mui/material';
import { Line } from 'react-chartjs-2';

function SensorTrendCard({ sensorName, latestValue, times, values }) {
  const data = {
    labels: times,
    datasets: [{
      label: sensorName,
      data: values,
      borderColor: '#1976d2',
      backgroundColor: 'rgba(25, 118, 210, 0.2)',
      fill: false,
      pointRadius: 2
    }]
  };

  const options = {
    responsive: true,
    plugins: {
      legend: { display: false },
      zoom: {
        pan: { enabled: true, mode: 'x' },
        zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: 'x' }
      }
    },
    scales: {
      x: {
        type: 'time',
        time: { unit: 'hour', stepSize: 1, displayFormats: { hour: 'HH:mm' } },
        grid: { color: '#eee', drawTicks: true },
        ticks: {
          major: { enabled: true },
          minor: { enabled: true, stepSize: 0.25 }
        }
      },
      y: { grid: { color: '#eee' } }
    }
  };

  return (
    <Card variant="outlined" sx={{ marginBottom: 2 }}>
      <CardContent>
        <Typography variant="h6">{sensorName}</Typography>
        <Typography variant="h4" sx={{ margin: 1 }}>{latestValue}</Typography>
        <Line data={data} options={options} />
      </CardContent>
    </Card>
  );
}

export default SensorTrendCard;
