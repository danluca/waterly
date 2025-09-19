// src/App.js
import * as React from 'react';
import {useEffect, useState} from "react";
import {Card, CardContent, Typography, Grid, Box, Container} from '@mui/material';
import {fetchSensors} from './api/sensors';
import {fetchManifest} from './api/manifest';
import YardIcon from '@mui/icons-material/Yard';
import WavesIcon from '@mui/icons-material/Waves';

const fmt = (v) => (typeof v === 'number' ? v.toLocaleString(undefined, {maximumFractionDigits: 2}) : v);

function SensorCard({title, value, unit, subtitle, secondaryLabel, secondaryValue, secondaryUnit}) {
    return (
        <Card variant="outlined" sx={{width: 240, height: 160, display: 'flex', flexDirection: 'column'}}>
            <CardContent
                sx={{display: 'flex', flexDirection: 'column', justifyContent: 'space-between', height: '100%'}}>
                <div>
                    <Typography variant="overline" color="text.secondary">
                        {subtitle || title}
                    </Typography>
                    <Typography variant="h6" sx={{mt: 0.5}}>
                        {title}
                    </Typography>
                    <Typography variant="h4" sx={{mt: 1}}>
                        {fmt(value)} <Typography component="span" variant="h6"
                                                 color="text.secondary">{unit}</Typography>
                    </Typography>
                </div>
                {secondaryValue !== undefined && (
                    <Typography variant="body2" color="text.secondary" sx={{mt: 0.75}}>
                        {secondaryLabel || 'Total'}: <strong>{fmt(secondaryValue)}</strong> {secondaryUnit}
                    </Typography>
                )}
            </CardContent>
        </Card>
    );
}

export default function App() {
    const [sensorData, setSensorData] = useState([]);
    const [manifest, setManifest] = useState(null);
    const currentYear = new Date().getFullYear();
    useEffect(() => {
        fetchSensors().then(setSensorData);
    }, []);
    useEffect(() => {
        fetchManifest().then(setManifest);
    }, []);

    return (
        <Container sx={{marginY: 4}}>
            <Box sx={{
                p: {xs: 2, sm: 3},
                mb: 3,
                borderRadius: 2,
                background: 'linear-gradient(135deg, #6EE7F9 0%, #A78BFA 35%, #F472B6 70%, #F59E0B 100%)',
                boxShadow: 4,
                position: 'relative',
                overflow: 'hidden',
            }}>
                <Box sx={{display: 'flex', alignItems: 'center', gap: 1.25}}>
                    <YardIcon sx={{color: '#065F46', fontSize: 34}}/>
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
                        WATERLY - Lucas Smarden - Watering Management System
                    </Typography>
                </Box>
                <Typography variant="subtitle2" sx={{color: 'rgba(255,255,255,0.92)', mt: 0.5}}>
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

            <Typography variant="h5" sx={{mb: 2}}>
                Latest readings
            </Typography>
            <Grid container spacing={2}>
                {(() => {
                    // Only include actual zones with names; handle weather separately
                    const weather = sensorData?.weather;
                    const zones = Object.values(sensorData || {}).filter(z => z && z.name);
                    const isRpiZone = (z) => z?.name === 'RPI' || /raspberry\s*pi/i.test(z?.desc || '');
                    zones.sort((a, b) => {
                        const ar = isRpiZone(a), br = isRpiZone(b);
                        if (ar && !br) return 1;
                        if (!ar && br) return -1;
                        return String(a?.name || '').localeCompare(String(b?.name || ''));
                    });
                    return (
                        <>
                            {zones.map((zone) => {
                                const metricDefs = [
                                    {key: 'temperature', label: 'Temperature', unitKey: 'temperature_unit'},
                                    {key: 'humidity', label: 'Humidity', unitKey: 'humidity_unit'},
                                    {key: 'ph', label: 'pH', unitKey: 'ph_unit'},
                                    {key: 'rpitemp', label: 'Temperature', unitKey: 'rpitemp_unit'},
                                ];
                                const metrics = metricDefs.filter(m => zone[m.key] !== undefined);
                                const hasWater = zone.water !== undefined || zone.total_water !== undefined;

                                // Backgrounds: Z1-Z3 pale green, RPI pale raspberry
                                const isRpi = isRpiZone(zone);
                                const zoneBg = isRpi ? '#FCE4EC' : '#E8F5E9'; // raspberry-ish vs pale green

                                return (
                                    <Grid item xs={12} key={zone.name}>
                                        <Card variant="outlined"
                                              sx={{p: 2, backgroundColor: zoneBg, borderColor: 'divider'}}>
                                            <Typography variant="overline" color="text.secondary">
                                                {zone.desc || 'Zone'}
                                            </Typography>
                                            <Typography variant="h6" sx={{mt: 0.5}}>
                                                • {zone.date} {zone.time ? `@ ${zone.time}` : ''}
                                            </Typography>
                                            <Grid container spacing={2} alignItems="stretch" sx={{mt: 0.5}}>
                                                {metrics.map(m => (
                                                    <Grid item key={`${zone.name}-${m.key}`} sx={{height: '100%'}}>
                                                        <SensorCard
                                                            //title={m.label}
                                                            value={zone[m.key]}
                                                            unit={zone[m.unitKey]}
                                                            subtitle={m.label}
                                                        />
                                                    </Grid>
                                                ))}
                                                {hasWater && (
                                                    <Grid item key={`${zone.name}-water`} sx={{height: '100%'}}>
                                                        <SensorCard
                                                            subtitle="Water"
                                                            value={zone.total_water}
                                                            unit={zone.water_unit}
                                                            secondaryLabel="Last"
                                                            secondaryValue={zone.water}
                                                            secondaryUnit={`${zone.water_unit}${zone.last_watering != null ? ` @ ${zone.last_watering}` : ''}`}
                                                        />
                                                    </Grid>
                                                )}
                                            </Grid>
                                        </Card>
                                    </Grid>
                                );
                            })}
                            {/* Weather "zone" after RPI */}
                            {weather && (
                                <Grid item xs={12} key="weather-zone">
                                    <Card variant="outlined"
                                          sx={{p: 2, backgroundColor: '#E3F2FD', borderColor: 'divider'}}>
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
                                        <Grid container spacing={2} alignItems="stretch" sx={{mt: 0.5}}>
                                            <Grid item sx={{height: '100%'}}>
                                                <SensorCard
                                                    subtitle="Previous 12h"
                                                    value={`${fmt(weather.prev12?.temp_min)} - ${fmt(weather.prev12?.temp_max)}`}
                                                    unit={weather.prev12?.temp_unit}
                                                    secondaryLabel="Rain"
                                                    secondaryValue={weather.prev12?.precip}
                                                    secondaryUnit={weather.prev12?.precip_unit}
                                                />
                                            </Grid>
                                            <Grid item sx={{height: '100%'}}>
                                                <SensorCard
                                                    subtitle="Next 12h"
                                                    value={`${fmt(weather.next12?.temp_min)} - ${fmt(weather.next12?.temp_max)}`}
                                                    unit={weather.next12?.temp_unit}
                                                    secondaryLabel="Rain"
                                                    secondaryValue={weather.next12?.precip}
                                                    secondaryUnit={`${weather.next12?.precip_unit}${weather.next12?.precip_prob != null ? ` - chance: ${fmt(weather.next12.precip_prob)}%` : ''}`}
                                                />
                                            </Grid>
                                        </Grid>
                                    </Card>
                                </Grid>
                            )}
                        </>
                    );
                })()}
            </Grid>
            <Box align="center" component="footer" sx={{
                mt: 6,
                pt: 2,
                pb: 3,
                borderTop: '1px solid',
                borderColor: 'divider',
                color: 'text.secondary',
            }}
            >
                <Typography variant="body2 ">
                    © {currentYear}{' '}
                    {manifest?.author} All rights reserved.
                    {manifest?.license ? ` • ${manifest.license} License` : ''}
                    {' • '} <a href={`${manifest?.git_url}`} target="_blank" rel="noopener noreferrer"
                               style={{marginLeft: '0.2rem'}}>
                    {`${manifest?.name} v${manifest?.version}`}
                </a> - {manifest?.description}
                    {' • '} <a href={`${manifest?.git_url}/commit/${manifest?.git_sha}`} target="_blank"
                               rel="noopener noreferrer" style={{marginLeft: '0.2rem'}}>
                    {`${manifest?.git_branch} @ ${manifest?.git_sha ? manifest.git_sha.slice(0, 8) : ''}`}
                </a>
                </Typography>
            </Box>

        </Container>
    );
}
