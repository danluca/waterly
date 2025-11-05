/*
 * MIT License
 *
 * Copyright (c) 2025 by Dan Luca. All rights reserved.
 *
 */

import * as React from 'react';
import {Box, Link, Typography} from '@mui/material';
import YardIcon from '@mui/icons-material/Yard';
import WavesIcon from '@mui/icons-material/Waves';

export default function Header() {
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
        <Typography variant="h5">Latest readings</Typography>
        <Link href="/settings" underline="hover" sx={{position:'absolute', right:32, backgroundColor:'#fff', fontFamily: 'Roboto', fontWeight: 400, p: '6px 10px', border: '1px solid', borderColor: 'divider', borderRadius: 1, boxShadow: 2, transition: 'background-color 0.2s ease', '&:hover': { backgroundColor: '#FFE8CC' }}}>Settings</Link>
      </Box>
    </>
  );
}
