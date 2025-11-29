/*
 * MIT License
 *
 * Copyright (c) 2025 by Dan Luca. All rights reserved.
 *
 */

import * as React from 'react';
import {useEffect, useState} from 'react';
import {Box, Typography} from '@mui/material';

export default function AboutPage() {
  const [about, setAbout] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError('');
      try {
        const resp = await fetch('/api/about');
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        if (!cancelled) setAbout(data);
      } catch (e) {
        if (!cancelled) setError(String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  return (
    <Box sx={{my: 3}}>
      <Typography variant="h4" gutterBottom>About</Typography>
      {loading && <Typography>Loading…</Typography>}
      {error && <Typography color="error">{error}</Typography>}
      {about && (
        <Box component="div" sx={{mt: 2}}>
          <Typography variant="body1" sx={{whiteSpace: 'pre-wrap'}}>
            OS: {about.os_name} {about.os_release} {about.os_version || ''}
          </Typography>
          <Typography variant="body1">Waterly: v{about.waterly_version} ({about.waterly_branch}@{about.waterly_sha})</Typography>
          {about.waterly_build_date && (
            <Typography variant="body1">Build date: {about.waterly_build_date}</Typography>
          )}
          {about.waterly_repo_url && (
            <Typography variant="body1">
              Repo: <a href={about.waterly_repo_url} target="_blank" rel="noreferrer">{about.waterly_repo_url}</a>
            </Typography>
          )}
          <Typography variant="body1">Time: {about.now} ({about.timezone})</Typography>
          <Typography variant="body1">IP: {about.ip_address} / {about.netmask} • MAC: {about.mac_address}</Typography>
          {about.wifi_ssid && (
            <Typography variant="body1">Wi‑Fi: {about.wifi_ssid} • RSSI: {about.wifi_rssi} dBm • Quality: {about.wifi_quality} • Bars: {about.wifi_bars}</Typography>
          )}

          <Box sx={{mt: 3}}>
            <Typography variant="overline" display="block">Raw</Typography>
            <pre style={{background: '#222', color: '#ddd', padding: '12px', borderRadius: 8, overflowX: 'auto'}}>
{about ? JSON.stringify(about, null, 2) : ''}
            </pre>
          </Box>
        </Box>
      )}
    </Box>
  );
}
