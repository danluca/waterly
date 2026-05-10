/*
 * MIT License
 *
 * Copyright (c) 2025 by Dan Luca. All rights reserved.
 *
 */

import * as React from 'react';
import {Button, Checkbox, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, FormControlLabel, Stack, TextField, Typography} from '@mui/material';

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
}) {
  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="xs">
      <DialogTitle>
        {`Water ${zone?.desc || zone?.name || ''}`}
      </DialogTitle>
      <DialogContent>
        <Stack spacing={1.25} sx={{mt: 0.5}}>
          <FormControlLabel control={<Checkbox checked={limitEnabled} onChange={(e)=>setLimitEnabled(e.target.checked)} />} label="Enable time limit" />
          <TextField type="number" label="Minutes" size="small" value={minutes} onChange={(e)=>setMinutes(e.target.value)} disabled={!limitEnabled} slotProps={{htmlInput: {min: 1}}} />
          {errorMsg && (
            <Typography variant="body2" color="error" sx={{mt:0.5}}>{errorMsg}</Typography>
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button onClick={onStop} disabled={!started}>Stop watering</Button>
        <Button variant="contained" onClick={onStart} disabled={starting}>
          {starting ? (<><CircularProgress size={16} sx={{mr:1}}/>Starting...</>) : 'Start watering'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
