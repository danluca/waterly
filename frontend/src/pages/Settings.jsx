/*
 * MIT License
 *
 * Copyright (c) 2025 by Dan Luca. All rights reserved.
 *
 */

import * as React from 'react';
import {useEffect, useMemo, useState} from 'react';
import {Container, Box, Typography, Grid, Card, CardContent, TextField, Button, Alert, Divider, Link, Select, MenuItem} from '@mui/material';
import {getConfig, postConfig} from '../api/config';
import SettingsIcon from '@mui/icons-material/Settings';
import WavesIcon from '@mui/icons-material/Waves';

function isReadOnlyKey(key) {
  return /last_|_last|_last_/i.test(key);
}

const friendlyLabels = {
  UNITS: 'Units',
  WEATHER_CHECK_INTERVAL_SECONDS: 'Weather check interval (mm:ss)',
  SENSOR_READ_INTERVAL_SECONDS: 'Sensor poll interval (mm:ss)',
  TREND_MAX_SAMPLES: 'Trend max size',
  WATERING_MAX_MINUTES_PER_ZONE: 'Watering max time (mm:ss)',
  WATERING_START_TIME: 'Watering start time (HH:MM)',
  RAIN_CANCEL_PROBABILITY_THRESHOLD: 'Rain cancel threshold (%)',
  WEATHER_CHECK_PRE_WATERING_SECONDS: 'Weather pre-check offset (mm:ss)',
  LOCAL_TIMEZONE: 'Local timezone',
  LAST_WATERING_DATE: 'Last watering date',
  WEATHER_LAST_CHECK_TIMESTAMP: 'Last weather check',
};

// Helpers to handle mm:ss formatting
function formatMMSS(totalSeconds) {
  const s = Math.max(0, Math.round(Number(totalSeconds || 0)));
  const mm = Math.floor(s / 60);
  const ss = s % 60;
  return `${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')}`;
}

function parseMMSS(input) {
  if (input == null) return 0;
  const str = String(input).trim();
  if (str === '') return 0;
  if (!str.includes(':')) {
    // Treat as minutes if plain number; convert to seconds
    const m = Number(str);
    return Number.isFinite(m) ? Math.max(0, Math.round(m)) * 60 : 0;
  }
  const [mStr, sStr] = str.split(':');
  const m = Number(mStr);
  const s = Number(sStr);
  const mm = Number.isFinite(m) ? Math.max(0, Math.floor(m)) : 0;
  const ss = Number.isFinite(s) ? Math.max(0, Math.min(59, Math.floor(s))) : 0;
  return mm * 60 + ss;
}

function normalizeConfig(obj) {
  // Ensure per-zone maps exist
  const out = {...obj};
  out.HUMIDITY_TARGET_PERCENT = out.HUMIDITY_TARGET_PERCENT || {};
  out.MINIMUM_SENSOR_HUMIDITY_PERCENT = out.MINIMUM_SENSOR_HUMIDITY_PERCENT || {};
  // Ensure LOCATION object exists for latitude/longitude editing
  out.LOCATION = out.LOCATION || {};
  // Ensure gardening season object exists (migrate from legacy start/end if present)
  const start = out.GARDENING_SEASON?.start ?? out.GARDENING_SEASON_START ?? '';
  const stop = out.GARDENING_SEASON?.stop ?? out.GARDENING_SEASON_END ?? '';
  out.GARDENING_SEASON = {start, stop};
  return out;
}

export default function SettingsPage() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);
  const [config, setConfig] = useState({});
  const [edited, setEdited] = useState({});

  useEffect(() => {
    (async () => {
      setLoading(true);
      setError(null);
      const {ok, data} = await getConfig();
      if (!ok) {
        setError('Failed to load configuration');
      }
      const cfg = normalizeConfig(data || {});
      setConfig(cfg);
      setEdited(cfg);
      setLoading(false);
    })();
  }, []);

  const zoneNames = useMemo(() => {
    const z = new Set([
      ...Object.keys(edited?.HUMIDITY_TARGET_PERCENT || {}),
      ...Object.keys(edited?.MINIMUM_SENSOR_HUMIDITY_PERCENT || {}),
    ]);
    return Array.from(z).sort();
  }, [edited]);

  const onFieldChange = (key, value) => {
    setEdited(prev => ({...prev, [key]: value}));
  };

  const onZoneChange = (mapKey, zone, value) => {
    setEdited(prev => ({...prev, [mapKey]: {...(prev[mapKey] || {}), [zone]: value}}));
  };

  // Build a minimal set of changes between original config and the edited values
  function buildChanges(original, updated) {
    const changes = {};

    const isPlainObject = (v) => v && typeof v === 'object' && !Array.isArray(v);

    const keys = new Set([
      ...Object.keys(updated || {}),
    ]);
    for (const key of keys) {
      if (isReadOnlyKey(key)) continue;
      const oldVal = original ? original[key] : undefined;
      const newVal = updated[key];

      // If both are plain objects, diff at field level
      if (isPlainObject(oldVal) && isPlainObject(newVal)) {
        const sub = {};
        const subKeys = new Set([...Object.keys(newVal || {})]);
        for (const sk of subKeys) {
          const ov = oldVal ? oldVal[sk] : undefined;
          const nv = newVal[sk];
          if (ov !== nv) {
            sub[sk] = nv;
          }
        }
        // Only include the object if there are any changed sub-keys
        if (Object.keys(sub).length > 0) {
          // Special rule: for HUMIDITY_TARGET_PERCENT, if any zone changes,
          // include the entire map (all zones) to keep triplets consistent.
          if (key === 'HUMIDITY_TARGET_PERCENT') {
            changes[key] = newVal;
          } else {
            changes[key] = sub;
          }
        }
      } else {
        // Primitive or differing types: include when changed
        if (oldVal !== newVal) {
          changes[key] = newVal;
        }
      }
    }

    return changes;
  }

  const save = async () => {
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      // Build minimal change set to send only modified values
      const changes = buildChanges(config, edited);
      if (Object.keys(changes).length === 0) {
        setMessage('No changes to save.');
        return;
      }
      const {ok, status, data} = await postConfig(changes);
      if (ok) {
        setMessage('Settings saved successfully.');
        if (data?.config) {
          const merged = normalizeConfig(data.config);
          setConfig(merged);
          setEdited(merged);
        }
      } else {
        const errs = data?.errors ? JSON.stringify(data.errors) : '';
        setError(`Save failed (status ${status}). ${errs}`);
      }
    } catch (e) {
      setError(`Save failed: ${String(e)}`);
    } finally {
      setSaving(false);
    }
  };

  const renderPrimitiveField = (key, val) => {
    const ro = isReadOnlyKey(key);
    const isNum = typeof val === 'number';
    const isStr = typeof val === 'string';
    const label = friendlyLabels[key] || key.replace(/_/g, ' ');
    if (!isNum && !isStr) return null;

    // Special control for UNITS dropdown
    if (key === 'UNITS') {
      return (
        <Grid item xs={12} sm={6} md={4} key={key}>
          <TextField
            select
            fullWidth
            label={label}
            value={edited[key]?.toLowerCase() ?? ''}
            onChange={e => onFieldChange(key, e.target.value)}
          >
            <MenuItem value="imperial">Imperial</MenuItem>
            <MenuItem value="metric">Metric</MenuItem>
          </TextField>
        </Grid>
      );
    }

    // Special mm:ss editor for second-based duration fields
    const secondsKeys = ['SENSOR_READ_INTERVAL_SECONDS', 'WEATHER_CHECK_INTERVAL_SECONDS', 'WEATHER_CHECK_PRE_WATERING_SECONDS'];
    if (secondsKeys.includes(key)) {
      const display = formatMMSS(edited[key] ?? 0);
      return (
        <Grid item xs={12} sm={6} md={4} key={key}>
          <TextField
            fullWidth
            label={label}
            value={display}
            disabled={ro}
            placeholder="mm:ss"
            onChange={e => onFieldChange(key, parseMMSS(e.target.value))}
          />
        </Grid>
      );
    }

    // Special mm:ss editor for minute-based field (store minutes)
    if (key === 'WATERING_MAX_MINUTES_PER_ZONE') {
      const minutes = Number(edited[key] ?? 0);
      const display = `${String(Math.max(0, Math.floor(minutes))).padStart(2, '0')}:00`;
      return (
        <Grid item xs={12} sm={6} md={4} key={key}>
          <TextField
            fullWidth
            label={label}
            value={display}
            disabled={ro}
            placeholder="mm:ss"
            onChange={e => {
              const secs = parseMMSS(e.target.value);
              const mins = Math.floor(secs / 60);
              onFieldChange(key, mins);
            }}
          />
        </Grid>
      );
    }

    return (
      <Grid item xs={12} sm={6} md={4} key={key}>
        <TextField
          fullWidth
          label={label}
          value={edited[key] ?? ''}
          disabled={ro}
          type={isNum ? 'number' : 'text'}
          slotProps={{htmlInput: isNum ? {step: 'any'} : {}}}
          onChange={e => onFieldChange(key, isNum ? Number(e.target.value) : e.target.value)}
        />
      </Grid>
    );
  };

  return (
    <Container sx={{my: 4}}>
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
          <SettingsIcon sx={{color: '#065F46', fontSize: 34}}/>
          <Typography variant="h4" sx={{
            fontWeight: 800,
            letterSpacing: 0.5,
            color: '#064E3B',
            textShadow: '0 2px 4px rgba(0,0,0,0.45)',
            backgroundClip: 'text',
            WebkitBackgroundClip: 'text',
            backgroundImage: 'inherit',
          }}>
          <Link href="/" underline="hover" sx={{color: '#064E3B'}}>Waterly</Link> - Settings
          </Typography>
        </Box>
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
      {loading && <Typography>Loading...</Typography>}
      {error && <Alert severity="error" sx={{mb: 2}}>{error}</Alert>}
      {message && <Alert severity="success" sx={{mb: 2}}>{message}</Alert>}

      {!loading && (
        <>
          <Card variant="outlined" sx={{mb: 2}}>
            <CardContent>
              <Typography variant="h6" sx={{mb: 1}}>General</Typography>
              <Grid container spacing={2}>
                {renderPrimitiveField('LOCAL_TIMEZONE', edited.LOCAL_TIMEZONE)}
                {renderPrimitiveField('UNITS', edited.UNITS)}
                {renderPrimitiveField('SENSOR_READ_INTERVAL_SECONDS', edited.SENSOR_READ_INTERVAL_SECONDS)}
                {renderPrimitiveField('TREND_MAX_SAMPLES', edited.TREND_MAX_SAMPLES)}
                {renderPrimitiveField('WATERING_MAX_MINUTES_PER_ZONE', edited.WATERING_MAX_MINUTES_PER_ZONE)}
                {renderPrimitiveField('WATERING_START_TIME', edited.WATERING_START_TIME)}
                {renderPrimitiveField('RAIN_CANCEL_PROBABILITY_THRESHOLD', edited.RAIN_CANCEL_PROBABILITY_THRESHOLD)}
                {renderPrimitiveField('WEATHER_CHECK_INTERVAL_SECONDS', edited.WEATHER_CHECK_INTERVAL_SECONDS)}
                {renderPrimitiveField('WEATHER_CHECK_PRE_WATERING_SECONDS', edited.WEATHER_CHECK_PRE_WATERING_SECONDS)}
                <Grid item xs={12} sm={6} md={4}>
                  <TextField
                    fullWidth
                    label="Gardening season start (MM-DD)"
                    value={edited.GARDENING_SEASON?.start ?? ''}
                    onChange={e => onFieldChange('GARDENING_SEASON', {...edited.GARDENING_SEASON, start: e.target.value})}
                  />
                </Grid>
                <Grid item xs={12} sm={6} md={4}>
                  <TextField
                    fullWidth
                    label="Gardening season end (MM-DD)"
                    value={edited.GARDENING_SEASON?.stop ?? ''}
                    onChange={e => onFieldChange('GARDENING_SEASON', {...edited.GARDENING_SEASON, stop: e.target.value})}
                  />
                </Grid>
              </Grid>
            </CardContent>
          </Card>

          <Card variant="outlined" sx={{mb: 2}}>
            <CardContent>
              <Typography variant="h6" sx={{mb: 1}}>Location</Typography>
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6} md={4}>
                  <TextField
                    fullWidth
                    label="Latitude"
                    type="number"
                    slotProps={{htmlInput: {step: 'any', min: -90, max: 90}}}
                    value={edited.LOCATION?.latitude ?? ''}
                    onChange={e => onFieldChange('LOCATION', {...edited.LOCATION, latitude: Number(e.target.value)})}
                  />
                </Grid>
                <Grid item xs={12} sm={6} md={4}>
                  <TextField
                    fullWidth
                    label="Longitude"
                    type="number"
                    slotProps={{htmlInput: {step: 'any', min: -180, max: 180}}}
                    value={edited.LOCATION?.longitude ?? ''}
                    onChange={e => onFieldChange('LOCATION', {...edited.LOCATION, longitude: Number(e.target.value)})}
                  />
                </Grid>
                {/* Google Maps link when both coordinates are present */}
                <Grid item xs={12} md={4}>
                  {(() => {
                    const lat = edited?.LOCATION?.latitude;
                    const lon = edited?.LOCATION?.longitude;
                    const valid = Number.isFinite(lat) && Number.isFinite(lon);
                    if (!valid) return null;
                    const url = `https://www.google.com/maps?q=${lat},${lon}`;
                    return (
                      <Box sx={{display: 'flex', alignItems: 'center', height: '100%'}}>
                        <Link href={url} target="_blank" rel="noopener" underline="hover">
                          See it in Google Maps ({lat.toFixed(5)}, {lon.toFixed(5)})
                        </Link>
                      </Box>
                    );
                  })()}
                </Grid>
              </Grid>
            </CardContent>
          </Card>

          <Card variant="outlined" sx={{mb: 2}}>
            <CardContent>
              <Typography variant="h6" sx={{mb: 1}}>Events</Typography>
              <Grid container spacing={2}>
                {renderPrimitiveField('LAST_WATERING_DATE', edited.LAST_WATERING_DATE)}
                {edited.WEATHER_LAST_CHECK_TIMESTAMP && (
                  <Grid item xs={12} sm={12} md={12} size={4} key={'WEATHER_LAST_CHECK_TIMESTAMP'}>
                    <TextField
                      fullWidth
                      label={friendlyLabels['WEATHER_LAST_CHECK_TIMESTAMP'] || 'WEATHER_LAST_CHECK_TIMESTAMP'}
                      value={(() => {
                        const ts = edited.WEATHER_LAST_CHECK_TIMESTAMP;
                        if (typeof ts === 'string') return ts;
                        try { return ts.iso || JSON.stringify(ts); } catch (_) { return String(ts); }
                      })()}
                      disabled
                    />
                  </Grid>
                )}
              </Grid>
            </CardContent>
          </Card>

          <Card variant="outlined" sx={{mb: 2}}>
            <CardContent>
              <Typography variant="h6" sx={{mb: 1}}>Zone settings</Typography>
              <Grid container spacing={2}>
                {zoneNames.map(z => (
                  <Grid item xs={12} md={6} key={`Z-${z}`}>
                    <Card variant="outlined">
                      <CardContent>
                        <Typography variant="subtitle1" sx={{mb: 1}}>Zone {z} Humidity</Typography>
                        <Grid container spacing={2}>
                          <Grid item xs={12} sm={6}>
                            <TextField
                              fullWidth
                              label="Target (%)"
                              type="number"
                              slotProps={{htmlInput: {step: '0.1', min: 0, max: 100}}}
                              value={edited.HUMIDITY_TARGET_PERCENT?.[z] ?? ''}
                              onChange={e => onZoneChange('HUMIDITY_TARGET_PERCENT', z, Number(e.target.value))}
                            />
                          </Grid>
                          <Grid item xs={12} sm={6}>
                            <TextField
                              fullWidth
                              label="Minimum (%)"
                              type="number"
                              slotProps={{htmlInput: {step: '0.1', min: 0, max: 100}}}
                              value={edited.MINIMUM_SENSOR_HUMIDITY_PERCENT?.[z] ?? ''}
                              onChange={e => onZoneChange('MINIMUM_SENSOR_HUMIDITY_PERCENT', z, Number(e.target.value))}
                            />
                          </Grid>
                        </Grid>
                      </CardContent>
                    </Card>
                  </Grid>
                ))}
              </Grid>
            </CardContent>
          </Card>

          <Box sx={{display: 'flex', gap: 2, alignItems: 'center'}}>
            <Button variant="contained" onClick={save} disabled={saving}>Save</Button>
            <Button variant="text" onClick={() => setEdited(config)} disabled={saving}>Reset</Button>
          </Box>
        </>
      )}

      <Divider sx={{my: 3}}/>

    </Container>
  );
}
