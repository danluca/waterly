// src/App.js
import * as React from 'react';
import { useState } from 'react';
import { Container } from '@mui/material';
import useAppData from './hooks/useAppData';
import Header from './components/Header';
import ZonesGrid from './components/ZonesGrid';
import Footer from './components/Footer';
import WaterDialog from './components/WaterDialog';
import SettingsPage from './pages/Settings';

export default function App() {
    // Watering dialog state
    const [waterDialogOpen, setWaterDialogOpen] = useState(false);
    const [selectedZone, setSelectedZone] = useState(null);
    const [limitEnabled, setLimitEnabled] = useState(true);
    const [minutes, setMinutes] = useState('10');
    const [starting, setStarting] = useState(false);
    const [started, setStarted] = useState(false);
    const [errorMsg, setErrorMsg] = useState('');
    const { sensorData, manifest } = useAppData();
    const path = (typeof window !== 'undefined' && window.location && window.location.pathname) ? window.location.pathname : '/';
    if (path.startsWith('/settings')) {
        return <SettingsPage/>;
    }

    // Handlers for watering dialog
    const openWaterDialog = (zone) => {
        setSelectedZone(zone);
        setWaterDialogOpen(true);
        setStarted(false);
        setStarting(false);
        setErrorMsg('');
    };
    const closeWaterDialog = () => {
        setWaterDialogOpen(false);
        setSelectedZone(null);
        setStarting(false);
        setErrorMsg('');
    };
    const handleStart = async () => {
        if (!selectedZone) return;
        setStarting(true);
        setErrorMsg('');
        try {
            const url = `/api/water/${encodeURIComponent(selectedZone.name)}/start` + (limitEnabled && minutes ? `?minutes=${encodeURIComponent(parseInt(minutes||'0',10))}` : '');
            const resp = await fetch(url, {method: 'POST', headers: {'Content-Type': 'application/json'}});
            if (!(resp.ok || resp.status === 202)) {
                const txt = await resp.text();
                throw new Error(txt || `HTTP ${resp.status}`);
            }
            setStarted(true);
        } catch (e) {
            setErrorMsg(String(e));
        } finally {
            setStarting(false);
        }
    };
    const handleStop = async () => {
        if (!selectedZone) return;
        setErrorMsg('');
        try {
            const url = `/api/water/${encodeURIComponent(selectedZone.name)}/stop`;
            const resp = await fetch(url, {method: 'POST', headers: {'Content-Type': 'application/json'}});
            if (!(resp.ok || resp.status === 202)) {
                const txt = await resp.text();
                throw new Error(txt || `HTTP ${resp.status}`);
            }
            setStarted(false);
            closeWaterDialog();
        } catch (e) {
            setErrorMsg(String(e));
        }
    };

    return (
        <Container sx={{marginY: 4}}>
            <Header />
            <ZonesGrid sensorData={sensorData} onOpenWaterDialog={(zone) => openWaterDialog(zone)} />
            <Footer manifest={manifest} />
            <WaterDialog
                open={waterDialogOpen}
                onClose={closeWaterDialog}
                zone={selectedZone}
                limitEnabled={limitEnabled}
                setLimitEnabled={setLimitEnabled}
                minutes={minutes}
                setMinutes={setMinutes}
                errorMsg={errorMsg}
                started={started}
                starting={starting}
                onStart={handleStart}
                onStop={handleStop}
            />
        </Container>
    );
}
