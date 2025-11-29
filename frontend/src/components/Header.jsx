/*
 * MIT License
 *
 * Copyright (c) 2025 by Dan Luca. All rights reserved.
 *
 */

import * as React from 'react';
import {Box, Link, Typography, Tooltip} from '@mui/material';
import YardIcon from '@mui/icons-material/Yard';
import WavesIcon from '@mui/icons-material/Waves';
import SignalWifi0BarIcon from '@mui/icons-material/SignalWifi0Bar';
import SignalWifi1BarIcon from '@mui/icons-material/SignalWifi1Bar';
import SignalWifi2BarIcon from '@mui/icons-material/SignalWifi2Bar';
import SignalWifi3BarIcon from '@mui/icons-material/SignalWifi3Bar';
import SignalWifi4BarIcon from '@mui/icons-material/SignalWifi4Bar';
import SignalWifiOffIcon from '@mui/icons-material/SignalWifiOff';

export default function Header({ sensorData }) {
  const wifiBars = (sensorData && sensorData.RPI && typeof sensorData.RPI.wifi_bars === 'number')
    ? Math.max(0, Math.min(4, Math.floor(sensorData.RPI.wifi_bars)))
    : null;

  const WifiIcon = (() => {
    if (wifiBars == null) return SignalWifiOffIcon;
    switch (wifiBars) {
      case 0: return SignalWifi0BarIcon;
      case 1: return SignalWifi1BarIcon;
      case 2: return SignalWifi2BarIcon;
      case 3: return SignalWifi3BarIcon;
      case 4: return SignalWifi4BarIcon;
      default: return SignalWifiOffIcon;
    }
  })();

  const wifiColor = wifiBars == null ? 'action.disabled'
    : wifiBars <= 1 ? '#dc2626'
    : wifiBars === 2 ? '#f59e0b'
    : '#16a34a';

  return (
    <>
      <Box sx={{
        p: {xs: 2, sm: 3},
        mb: 3,
        borderRadius: 2,
        background: 'linear-gradient(135deg, #6EE7F9 0%, #A78BFA 35%, #F472B6 70%, #F59E0B 100%)',
        boxShadow: 4,
        position: 'relative',
        overflow: 'hidden',
      }}>
        <Link href="/" underline="hover">
            <Box sx={{display: 'flex', alignItems: 'center', gap: 1.25}}>
              <YardIcon sx={{color: '#065F46', fontSize: 34}}/>
              <Typography variant="h4" sx={{
                fontWeight: 800,
                letterSpacing: 0.5,
                color: '#064E3B',
                textShadow: '0 2px 4px rgba(0,0,0,0.45)',
                backgroundClip: 'text',
                WebkitBackgroundClip: 'text',
                backgroundImage: 'inherit',
              }}>
                WATERLY - Lucas Smarden - Watering Management System
              </Typography>
            </Box>
        </Link>
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

      <Box sx={{display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2}}>
        <Typography variant="h5">Readings</Typography>
        <Box sx={{position:'absolute', right:32, display:'flex', alignItems:'center', gap: 1.25}}>
          <Tooltip title={`Wi‑Fi signal ${wifiBars == null ? 'unknown' : wifiBars + ' bars'}`} placement="bottom">
            <Box aria-label="wifi-signal" sx={{display:'flex', alignItems:'center', mr: 0.5}}>
              <WifiIcon sx={{ color: wifiColor }} />
            </Box>
          </Tooltip>
          <Link href="/settings" underline="hover" sx={{backgroundColor:'#fff', fontFamily: 'Roboto', fontWeight: 400, p: '6px 10px', border: '1px solid', borderColor: 'divider', borderRadius: 1, boxShadow: 2, transition: 'background-color 0.2s ease', '&:hover': { backgroundColor: '#FFE8CC' }}}>Settings</Link>
          <Link href="/about" underline="hover" sx={{backgroundColor:'#fff', fontFamily: 'Roboto', fontWeight: 400, p: '6px 10px', border: '1px solid', borderColor: 'divider', borderRadius: 1, boxShadow: 2, transition: 'background-color 0.2s ease', '&:hover': { backgroundColor: '#FFE8CC' }}}>About</Link>
        </Box>
      </Box>
    </>
  );
}
