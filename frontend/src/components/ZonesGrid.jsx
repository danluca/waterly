/*
 * MIT License
 *
 * Copyright (c) 2025 by Dan Luca. All rights reserved.
 *
 */

import * as React from 'react';
import {Box, Card, Grid, Typography} from '@mui/material';
import SensorCard from './SensorCard';
import { fmt } from '../utils/format';

const ZONE_STYLE = {
  RPI: { bg: '#FCE4EC', cols: 1 },
  ENV: { bg: '#E0F7FA', cols: 2 },
};

const METRIC_DEFS = [
  {key: 'temperature',  label: 'Temperature', unitKey: 'temperature_unit'},
  {key: 'humidity',     label: 'Humidity',    unitKey: 'humidity_unit'},
  {key: 'ph',           label: 'pH',          unitKey: 'ph_unit'},
  {key: 'nitrogen',     label: 'N',           unitKey: 'nitrogen_unit'},
  {key: 'phosphorus',   label: 'P',           unitKey: 'phosphorus_unit'},
  {key: 'potassium',    label: 'K',           unitKey: 'potassium_unit'},
  {key: 'rpitemp',      label: 'Temperature', unitKey: 'rpitemp_unit'},
  {key: 'envtemp',      label: 'Temperature', unitKey: 'envtemp_unit'},
  {key: 'envhumidity',  label: 'Humidity',    unitKey: 'envhumidity_unit'},
];

export default function ZonesGrid({ sensorData, onOpenWaterDialog }) {
  const weather = sensorData?.weather;
  const zones = Object.values(sensorData || {}).filter(z => z && z.name);

  const specialRank = (z) => {
    const n = (z?.name || '').toUpperCase();
    if (n === 'RPI') return 1;
    if (n === 'ENV') return 2;
    return 0;
  };

  zones.sort((a, b) => {
    const ra = specialRank(a), rb = specialRank(b);
    if (ra !== rb) return ra - rb;
    return String(a?.name || '').localeCompare(String(b?.name || ''));
  });

  return (
    <Grid container spacing={2}>
      {zones.map((zone) => {
        const metrics = METRIC_DEFS.filter(m => zone[m.key] !== undefined);
        const hasWater = zone.water !== undefined || zone.total_water !== undefined;

        const n = String(zone?.name || '').toUpperCase();
        const { bg: zoneBg = '#E8F5E9', cols: desiredCols = 4 } = ZONE_STYLE[n] || {};
        const smCols = Math.min(2, desiredCols);

        return (
          <Grid item xs={12} key={zone.name}>
            <Card variant="outlined" sx={{p: 2, backgroundColor: zoneBg, borderColor: 'divider'}}>
              <Typography variant="overline" color="text.secondary">
                {zone.desc || 'Zone'}
              </Typography>
              <Typography variant="h6" sx={{mt: 0.5}}>
                • {zone.date} {zone.time ? `@ ${zone.time}` : ''}
              </Typography>
              <Box sx={{
                mt: 0.5,
                display: 'grid',
                gap: 2,
                gridTemplateColumns: {
                  xs: '1fr',
                  sm: `repeat(${smCols}, 1fr)`,
                  md: `repeat(${desiredCols}, 1fr)`
                },
                maxWidth: { md: `calc(${desiredCols} * 230px + ${desiredCols} * 16px)` },
                mx: { md: 'auto' }
              }}>
                {metrics.map(m => {
                  const prevMin = zone[`${m.key}_prev12_min`];
                  const prevMax = zone[`${m.key}_prev12_max`];
                  const showPrev = prevMin !== undefined && prevMax !== undefined;
                  return (
                    <Box key={`${zone.name}-${m.key}`} sx={{height: '100%'}}>
                      <SensorCard
                        value={zone[m.key]}
                        unit={zone[m.unitKey]}
                        subtitle={m.label}
                        {...(showPrev ? {
                          secondaryLabel: 'Prev 12h',
                          secondaryValue: `${fmt(prevMin)} - ${fmt(prevMax)}`,
                          secondaryUnit: zone[m.unitKey]
                        } : {})}
                      />
                    </Box>
                  );
                })}
                {hasWater && (
                  <Box key={`${zone.name}-water`} sx={{height: '100%'}}>
                    <SensorCard subtitle="Water"
                      value={zone.total_water}
                      unit={zone.water_unit}
                      secondaryLabel="Last"
                      secondaryValue={zone.water}
                      secondaryUnit={`${zone.water_unit}${zone.last_watering != null ? ` @ ${zone.last_watering}` : ''}`}
                      bgColor={zone.water_state ? '#cae7fc' : undefined}
                      onClick={() => onOpenWaterDialog(zone)}
                    />
                  </Box>
                )}
              </Box>
            </Card>
          </Grid>
        );
      })}

      {weather && (
        <Grid item xs={12} key="weather-zone">
          <Card variant="outlined" sx={{p: 2, backgroundColor: '#E3F2FD', borderColor: 'divider'}}>
            <Typography variant="overline" color="text.secondary">
              Forecast
            </Typography>
            {(() => {
              const nowUtc = weather.timestamp?.utc;
              const fcUtc = weather.forecast_time?.utc;
              let ageStr = null;
              if (nowUtc && fcUtc) {
                const diffSec = Math.max(0, nowUtc - fcUtc);
                const h = Math.floor(diffSec / 3600);
                const m = Math.floor((diffSec % 3600) / 60);
                const hh = String(h).padStart(2, '0');
                const mm = String(m).padStart(2, '0');
                ageStr = `${hh}:${mm} hrs`;
              }
              return (
                <Typography variant="h6" sx={{mt: 0.5}}>
                  • {weather.timestamp?.date} {weather.timestamp?.time ? `@ ${weather.timestamp.time}` : ''}{ageStr ? ` (age ${ageStr})` : ''}
                </Typography>
              );
            })()}
            <Grid container spacing={3} sx={{mt: 0.5}}>
              {/* Previous 12h group */}
              <Grid item xs={12} sm="auto">
                <Typography variant="caption" color="text.secondary" sx={{fontWeight: 'bold', display: 'block', mb: 1}}>
                  Previous 12h
                </Typography>
                <Grid container spacing={2} alignItems="stretch">
                  <Grid item sx={{height: '100%', backgroundColor: '#F1F2F3'}}>
                    <SensorCard subtitle="Temperature"
                      value={`${fmt(weather.prev12?.temp_min)} - ${fmt(weather.prev12?.temp_max)}`}
                      unit={weather.prev12?.temp_unit}
                      bgColor={'#F1F2F3'}
                    />
                  </Grid>
                  <Grid item sx={{height: '100%', backgroundColor: '#F1F2F3'}}>
                    <SensorCard subtitle="Moisture"
                      value={`${fmt(weather.prev12?.soil_moisture_min)} - ${fmt(weather.prev12?.soil_moisture_max)}`}
                      unit={weather.prev12?.soil_moisture_unit}
                      secondaryLabel="Rain"
                      secondaryValue={weather.prev12?.precip}
                      secondaryUnit={weather.prev12?.precip_unit}
                      bgColor={'#F1F2F3'}
                    />
                  </Grid>
                </Grid>
              </Grid>
              {/* Next 12h group */}
              <Grid item xs={12} sm="auto">
                <Typography variant="caption" color="text.secondary" sx={{fontWeight: 'bold', display: 'block', mb: 1}}>
                  Next 12h
                </Typography>
                <Grid container spacing={2} alignItems="stretch">
                  <Grid item sx={{height: '100%'}}>
                    <SensorCard subtitle="Temperature"
                      value={`${fmt(weather.next12?.temp_min)} - ${fmt(weather.next12?.temp_max)}`}
                      unit={weather.next12?.temp_unit}
                    />
                  </Grid>
                  <Grid item sx={{height: '100%'}}>
                    <SensorCard subtitle="Moisture"
                      value={`${fmt(weather.next12?.soil_moisture_min)} - ${fmt(weather.next12?.soil_moisture_max)}`}
                      unit={weather.next12?.soil_moisture_unit}
                      secondaryLabel="Rain"
                      secondaryValue={weather.next12?.precip}
                      secondaryUnit={`${weather.next12?.precip_unit}${weather.next12?.precip_prob != null ? ` - chance: ${fmt(weather.next12.precip_prob, 0)}%` : ''}`}
                    />
                  </Grid>
                </Grid>
              </Grid>
            </Grid>
          </Card>
        </Grid>
      )}
    </Grid>
  );
}
