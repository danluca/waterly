/*
 * MIT License
 *
 * Copyright (c) 2025 by Dan Luca. All rights reserved.
 *
 */

import * as React from 'react';
import {Box, Typography} from '@mui/material';

export default function Footer({ manifest }) {
  const currentYear = new Date().getFullYear();
  return (
    <Box align="center" component="footer" sx={{
      mt: 6,
      pt: 2,
      pb: 3,
      borderTop: '1px solid',
      borderColor: 'divider',
      color: 'text.secondary',
    }}>
      <Typography variant="body2 ">
        © {currentYear}{' '}
        {manifest?.author} All rights reserved.
        {manifest?.license ? ` • ${manifest.license} License` : ''}
        {' • '} <a href={`${manifest?.git_url}`} target="_blank" rel="noopener noreferrer" style={{marginLeft: '0.2rem'}}>
          {`${manifest?.name} v${manifest?.version}`}
        </a> - {manifest?.description}
        {' • '} <a href={`${manifest?.git_url}/tree/${manifest?.git_sha}`} target="_blank" rel="noopener noreferrer" style={{marginLeft: '0.2rem'}}>
          {`${manifest?.git_branch} @ ${manifest?.git_sha ? manifest.git_sha.slice(0, 8) : ''}`}
        </a>
      </Typography>
    </Box>
  );
}
