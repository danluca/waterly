/*
 * MIT License
 *
 * Copyright (c) 2025 by Dan Luca. All rights reserved.
 *
 */

import * as React from 'react';
import {Box, Link, Typography} from '@mui/material';

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
      <Typography variant="body2">
        © {currentYear}{' '}
        {manifest?.author} All rights reserved.
        {manifest?.license ? ` • ${manifest.license} License` : ''}
        {' • '}<Link href={manifest?.git_url} target="_blank" rel="noopener noreferrer" sx={{mx: 0.5}}>
          {`${manifest?.name} v${manifest?.version}`}
        </Link>- {manifest?.description}
        {' • '}<Link href={`${manifest?.git_url}/tree/${manifest?.git_sha}`} target="_blank" rel="noopener noreferrer" sx={{mx: 0.5}}>
          {`${manifest?.git_branch} @ ${manifest?.git_sha ? manifest.git_sha.slice(0, 8) : ''}`}
        </Link>
      </Typography>
    </Box>
  );
}
