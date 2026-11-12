/*
 * MIT License
 *
 * Copyright (c) by Dan Luca. All rights reserved.
 *
 */

import * as React from 'react';
import {Alert, Button, Checkbox, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, FormControlLabel, Stack, TextField, Typography} from '@mui/material';

export default function WaterDialog({
  open,
  onClose,
  zone,
  limitEnabled,
  setLimitEnabled,
  minutes,
  setMinutes,
  errorMsg,
  started,
  starting,
  onStart,
  onStop,
  wateringBlocked,
  wateringActive,
}) {
  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="xs">
      <DialogTitle>
        {`Water ${zone?.desc || zone?.name || ''}`}
      </DialogTitle>
      <DialogContent>
        <Stack spacing={1.25} sx={{mt: 0.5}}>
          {wateringBlocked && <Alert severity="info">Watering is unavailable while winterized, purging, or maintenance status is loading.</Alert>}
          <FormControlLabel control={<Checkbox checked={limitEnabled} onChange={(e)=>setLimitEnabled(e.target.checked)} />} label="Enable time limit" />
          <TextField type="number" label="Minutes" size="small" value={minutes} onChange={(e)=>setMinutes(e.target.value)} disabled={!limitEnabled} slotProps={{htmlInput: {min: 1}}} />
          {errorMsg && (
            <Typography variant="body2" color="error" sx={{mt:0.5}}>{errorMsg}</Typography>
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button onClick={onStop} disabled={!started && !wateringActive}>Stop watering</Button>
        <Button variant="contained" onClick={onStart} disabled={starting || wateringBlocked}>
          {starting ? (<><CircularProgress size={16} sx={{mr:1}}/>Starting...</>) : 'Start watering'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
