import * as React from 'react';
import {useEffect, useState} from 'react';
import {Alert, Box, Button, Card, CardContent, Chip, Dialog, DialogActions, DialogContent,
    DialogTitle, FormControlLabel, MenuItem, Stack, Switch, TextField, Typography} from '@mui/material';

const emptySensor = {name: '', type: 'SEN0604', address: '', zone_id: null, enabled: true};
const typeLabels = {SEN0604: 'SEN0604 — Soil moisture, temperature, pH, EC',
    SEN0605: 'SEN0605 — Nitrogen, phosphorus, potassium', SEN0438: 'SEN0438 — Air temperature and humidity'};

async function api(path = '', options) {
    const response = await fetch(`/api/sensors${path}`, options);
    const data = await response.json();
    if (!response.ok) throw new Error(data.message || `Request failed (${response.status})`);
    return data;
}

function timeLabel(value) {
    return value ? new Date(value).toLocaleString() : 'Never';
}

export default function SensorPanel() {
    const [data, setData] = useState({sensors: [], zones: [], types: []});
    const [error, setError] = useState('');
    const [message, setMessage] = useState('');
    const [draft, setDraft] = useState(null);
    const [formError, setFormError] = useState('');
    const [saving, setSaving] = useState(false);
    const [testing, setTesting] = useState(null);
    const [loaded, setLoaded] = useState(false);

    useEffect(() => {
        let mounted = true;
        async function refresh() {
            try {
                const result = await api();
                if (mounted) { setData(result); setError(''); setLoaded(true); }
            } catch (e) { if (mounted) setError(e.message); }
        }
        refresh();
        const timer = setInterval(refresh, 5000);
        return () => { mounted = false; clearInterval(timer); };
    }, []);

    const edit = sensor => { setDraft({...sensor}); setFormError(''); setMessage(''); };
    const field = (key, value) => setDraft(current => ({...current, [key]: value}));
    const save = async event => {
        event.preventDefault();
        setSaving(true);
        setFormError('');
        try {
            const result = await api(draft.id ? `/${draft.id}` : '', {
                method: draft.id ? 'PUT' : 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(draft),
            });
            setDraft(null);
            setMessage(result.message);
            setData(await api());
        } catch (e) { setFormError(e.message); }
        finally { setSaving(false); }
    };
    const test = async sensor => {
        setTesting(sensor.id);
        setMessage('');
        try {
            const result = await api(`/${sensor.id}/test`, {method: 'POST'});
            setMessage(result.message);
            setData(await api());
        } catch (e) { setError(e.message); }
        finally { setTesting(null); }
    };

    const compatibleZones = draft ? data.zones.filter(z => draft.type === 'SEN0438' ? z.name === 'ENV' : !!z.relay_address) : [];

    return <Stack spacing={2}>
        <Typography>Manage installed RS485 sensors and their zone assignments. Changes apply when watering is idle.</Typography>
        <Alert severity="info">A zone without an enabled, responding soil moisture sensor uses timed watering. Unassigned sensors are available for testing but are not polled.</Alert>
        {error && <Alert severity="error">{error}</Alert>}
        {message && <Alert severity="success">{message}</Alert>}
        <Box><Button variant="contained" disabled={!loaded} onClick={() => edit(emptySensor)}>Add sensor</Button></Box>
        {loaded && !data.sensors.length && <Typography>No sensors configured. Add a sensor to begin.</Typography>}
        {data.sensors.map(sensor => <Card variant="outlined" key={sensor.id}><CardContent>
            <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                <Typography variant="h6">{sensor.name}</Typography>
                <Chip size="small" label={sensor.status} color={sensor.status === 'responding' ? 'success' : sensor.status === 'offline' ? 'error' : 'default'} />
                {sensor.pending && <Chip size="small" label="Changes pending" color="warning" />}
                {sensor.test_pending && <Chip size="small" label="Test queued" color="info" />}
            </Stack>
            <Typography>{sensor.type} · Address {sensor.address} (0x{sensor.address.toString(16).toUpperCase().padStart(2, '0')}) · {sensor.zone || 'Unassigned'}</Typography>
            <Typography variant="body2">Last successful reading: {timeLabel(sensor.last_seen)}</Typography>
            {sensor.last_reading && <Typography variant="body2">{Object.entries(sensor.last_reading).map(([key, value]) => `${key.replaceAll('_', ' ')}: ${value}`).join(' · ')} (sensor units)</Typography>}
            {sensor.last_error && <Alert severity="warning" sx={{my: 1}}>{sensor.last_error}</Alert>}
            {sensor.tested_at && <Typography variant="body2">Connection test {sensor.test_success ? 'passed' : 'failed'}: {timeLabel(sensor.tested_at)}{sensor.test_error ? ` — ${sensor.test_error}` : ''}</Typography>}
            <Stack direction="row" spacing={1} sx={{mt: 1}}>
                <Button onClick={() => edit(sensor)}>Edit</Button>
                <Button disabled={sensor.test_pending || testing === sensor.id} onClick={() => test(sensor)}>Test connection</Button>
            </Stack>
        </CardContent></Card>)}
        <Dialog open={!!draft} onClose={() => !saving && setDraft(null)} fullWidth maxWidth="sm">
            {draft && <Box component="form" onSubmit={save}>
                <DialogTitle>{draft.id ? 'Edit sensor' : 'Add sensor'}</DialogTitle>
                <DialogContent><Stack spacing={2} sx={{pt: 1}}>
                    {formError && <Alert severity="error">{formError}</Alert>}
                    <TextField label="Name" value={draft.name} required inputProps={{maxLength: 80}} onChange={e => field('name', e.target.value)} />
                    <TextField select label="Type" value={draft.type} onChange={e => setDraft({...draft, type: e.target.value, zone_id: null})}>
                        {data.types.map(type => <MenuItem value={type} key={type}>{typeLabels[type] || type}</MenuItem>)}
                    </TextField>
                    <TextField label="RS485 address" value={draft.address} required onChange={e => field('address', e.target.value)}
                        helperText="1–247, decimal or hex (e.g. 10 or 0x0A). Sets the address GardenPy contacts; the device must already use it." />
                    <TextField select label="Zone" value={draft.zone_id ?? ''} onChange={e => field('zone_id', e.target.value === '' ? null : Number(e.target.value))}>
                        <MenuItem value="">Unassigned</MenuItem>
                        {compatibleZones.map(zone => <MenuItem value={zone.id} key={zone.id}>{zone.name} — {zone.description}</MenuItem>)}
                    </TextField>
                    <Typography variant="body2">Each zone supports one sensor of each compatible type. Addresses remain reserved while disabled.</Typography>
                    <FormControlLabel label="Enabled for polling" control={<Switch checked={draft.enabled} onChange={e => field('enabled', e.target.checked)} />} />
                    {!draft.enabled && <Alert severity="info">Disabled sensors retain their configuration and can still be tested.</Alert>}
                </Stack></DialogContent>
                <DialogActions><Button disabled={saving} onClick={() => setDraft(null)}>Cancel</Button><Button type="submit" variant="contained" disabled={saving}>{saving ? 'Saving…' : 'Save'}</Button></DialogActions>
            </Box>}
        </Dialog>
    </Stack>;
}
