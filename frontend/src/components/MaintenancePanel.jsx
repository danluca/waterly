import * as React from 'react';
import {useEffect, useState} from 'react';
import {Alert, Button, Card, CardContent, MenuItem, Stack, TextField, Typography} from '@mui/material';
import useMaintenanceStatus from '../hooks/useMaintenanceStatus';

export default function MaintenancePanel({sensorData, onStatusChange}) {
  const {status, error: statusError, refresh} = useMaintenanceStatus();
  const [zone, setZone] = useState('');
  const [seconds, setSeconds] = useState('60');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const zones = Object.values(sensorData || {}).filter(z => z?.name && z.water_state !== undefined);
  useEffect(() => {
    if (status) onStatusChange?.(status);
  }, [status, onStatusChange]);

  const act = async (url, body) => {
    setBusy(true);
    setError('');
    try {
      const response = await fetch(url, {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body || {}),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.message || 'Operation failed.');
    } catch (e) {
      setError(e.message);
    } finally {
      await refresh().catch(() => {});
      setBusy(false);
    }
  };

  const active = status?.active;
  const selectedZone = zone || zones[0]?.name || '';
  const duration = Number(seconds);
  const validDuration = Number.isInteger(duration) && duration >= 1 && duration <= (status?.max_seconds || 600);
  return (
    <Card variant="outlined" sx={{my: 2}}>
      <CardContent>
        <Stack spacing={2}>
          <Typography variant="h6">Winterize / air purge</Typography>
          <Typography variant="body2">
            Isolate the water supply and connect your regulated air supply before starting.
            Purging opens one zone valve; you control the air supply. Scheduled watering pauses during a purge.
          </Typography>
          {(error || statusError) && <Alert severity="error">{error || statusError}</Alert>}
          {status?.winterized && <Alert severity="info">Winterized: manual and scheduled watering are blocked until you re-enable watering. Air purging remains available.</Alert>}
          {status?.watering && <Alert severity="info">Watering is active. Stop it before starting a purge or changing winterized mode.</Alert>}
          {active && <Alert severity={active.error ? 'error' : 'info'}>
            Purging {active.zone}: {active.remaining_seconds}s remaining.
            {active.error && ` Could not finish: ${active.error}. Retrying; watering remains blocked.`}
          </Alert>}
          <Stack direction={{xs: 'column', sm: 'row'}} spacing={2}>
            <TextField select label="Purge zone" value={selectedZone} onChange={e => setZone(e.target.value)} disabled={busy || !!active} sx={{minWidth: 180}}>
              {zones.map(z => <MenuItem key={z.name} value={z.name}>{z.desc || z.name}</MenuItem>)}
            </TextField>
            <TextField label="Duration (seconds)" type="number" value={seconds} onChange={e => setSeconds(e.target.value)}
              disabled={busy || !!active} slotProps={{htmlInput: {min: 1, max: status?.max_seconds || 600, step: 1}}} />
            <Button variant="contained" disabled={!status || busy || !!active || status.watering || !selectedZone || !validDuration}
              onClick={() => act(`/api/purge/${encodeURIComponent(selectedZone)}/start`, {seconds: duration})}>Start purge</Button>
            <Button color="error" variant="outlined" disabled={busy || !active} onClick={() => act('/api/purge/stop')}>Stop purge</Button>
          </Stack>
          <Button sx={{alignSelf: 'flex-start'}} variant="outlined" disabled={!status || busy || !!active || status.watering}
            onClick={() => act('/api/maintenance/winterized', {winterized: !status.winterized})}>
            {status?.winterized ? 'Re-enable watering' : 'Mark system winterized'}
          </Button>
          {!status?.winterized && <Typography variant="caption">Mark the system winterized before seasonal purging to keep watering disabled between zones and across restarts. Re-enabling restores the configured schedule.</Typography>}
          {!!status?.history?.length && <>
            <Typography variant="subtitle2">Recent purges</Typography>
            {status.history.map(entry => <Typography variant="body2" key={entry.id}>
              {new Date(entry.started_at).toLocaleString()} · {entry.zone} · {entry.requested_seconds}s requested
              {entry.duration_seconds != null ? ` · ${Math.round(entry.duration_seconds)}s elapsed` : ''} · {entry.outcome}
            </Typography>)}
          </>}
        </Stack>
      </CardContent>
    </Card>
  );
}
