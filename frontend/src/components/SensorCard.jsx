/*
 * MIT License
 *
 * Copyright (c) 2025 by Dan Luca. All rights reserved.
 *
 */

import * as React from 'react';
import {Card, CardContent, Typography} from '@mui/material';
import { fmt } from '../utils/format';

export default function SensorCard({title, value, unit, subtitle, secondaryLabel, secondaryValue, secondaryUnit, bgColor, onClick}) {
    const hoverSx = onClick ? {'&:hover': { backgroundColor: '#FFE8CC' }} : {};
    return (
        <Card variant="outlined" onClick={onClick} sx={{width: 230, height: 160, display: 'flex', flexDirection: 'column', backgroundColor: bgColor, cursor: onClick ? 'pointer' : 'default', transition: 'background-color 0.2s ease', ...hoverSx}}>
            <CardContent sx={{display: 'flex', flexDirection: 'column', justifyContent: 'space-between', height: '100%'}}>
                <div>
                    <Typography variant="overline" color="text.secondary">
                        {subtitle || title}
                    </Typography>
                    <Typography variant="h6" sx={{mt: 0.5}}>
                        {title}
                    </Typography>
                    <Typography variant="h4" sx={{mt: 1}}>
                        {fmt(value)} <Typography component="span" variant="h6" color="text.secondary">{unit}</Typography>
                    </Typography>
                </div>
                {secondaryValue !== undefined && (
                    <Typography variant="body2" color="text.secondary" sx={{mt: 0.75}} noWrap title={`${secondaryLabel || 'Total'}: ${fmt(secondaryValue)} ${secondaryUnit || ''}`}>{secondaryLabel || 'Total'}: <strong>{fmt(secondaryValue)}</strong> {secondaryUnit}
                    </Typography>
                )}
            </CardContent>
        </Card>
    );
}
