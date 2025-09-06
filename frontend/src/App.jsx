// src/App.js
import * as React from 'react';
import {useEffect, useState} from "react";
import { Card, CardContent, Typography, Grid, Box, Container } from '@mui/material';
import { fetchSensors, fetchGroupedSensors } from './api/sensors';
import YardIcon from '@mui/icons-material/Yard';
import WavesIcon from '@mui/icons-material/Waves';

function SensorCard({ title, value, unit, subtitle }) {
  return (
    <Card variant="outlined" sx={{ minWidth: 240 }}>
      <CardContent>
        <Typography variant="overline" color="text.secondary">
          {subtitle || 'Sensor'}
        </Typography>
        <Typography variant="h6" sx={{ mt: 0.5 }}>
          {title}
        </Typography>
        <Typography variant="h4" sx={{ mt: 1 }}>
          {value} <Typography component="span" variant="h6" color="text.secondary">{unit}</Typography>
        </Typography>
      </CardContent>
    </Card>
  );
}

export default function App() {
  const [sensorData, setSensorData] = useState([]);
  useEffect(() => {
    fetchSensors().then(setSensorData);
  }, []);

  return (
    <Container sx={{ marginY: 4 }}>
        <Box sx={{
          p: { xs: 2, sm: 3 },
          mb: 3,
          borderRadius: 2,
          background: 'linear-gradient(135deg, #6EE7F9 0%, #A78BFA 35%, #F472B6 70%, #F59E0B 100%)',
          boxShadow: 4,
          position: 'relative',
          overflow: 'hidden',
        }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25 }}>
          <YardIcon sx={{ color: '#065F46', fontSize: 34 }} />
        <Typography variant="h4" sx={{
            fontWeight: 800,
            letterSpacing: 0.5,
            color: '#064E3B', // deep green for strong contrast
            textShadow: '0 2px 4px rgba(0,0,0,0.45)',
            backgroundClip: 'text',
            WebkitBackgroundClip: 'text',
            // WebkitTextFillColor: 'transparent',
            backgroundImage: 'inherit',
          }}>
          Lucas Smart Garden - Watering Management System
        </Typography>
        </Box>
        <Typography variant="subtitle2" sx={{ color: 'rgba(255,255,255,0.92)', mt: 0.5 }}>
          Monitor and manage your garden in real time
        </Typography>
            <WavesIcon
          sx={{
            position: 'absolute',
            right: -8,
            bottom: -10,
            fontSize: 120,
            color: 'rgba(255,255,255,0.18)',
            pointerEvents: 'none',
            transform: 'rotate(-8deg)',
          }}
        />
      </Box>

      <Typography variant="h5" sx={{ mb: 2 }}>
        Latest readings — {sensorData.time}
      </Typography>
      <Grid container spacing={2}>
        {sensorData?.measurements?.map((c) => (
          <Grid item key={c.name}>
            <SensorCard title={c.name} value={c.latestValue} unit={c.unit} subtitle={c.group ?? sensorData.site} />
          </Grid>
        ))}
      </Grid>
    </Container>
  );
}
