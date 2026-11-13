import * as React from 'react';
import {Box, Divider, Stack, Typography} from '@mui/material';
import MaintenancePanel from '../components/MaintenancePanel';
import SensorPanel from '../components/SensorPanel';

export default function ToolsPage({sensorData}) {
    return <Stack spacing={3}>
        <MaintenancePanel sensorData={sensorData} />
        <Divider />
        <Box component="section" id="sensors" aria-labelledby="sensors-heading">
            <Typography id="sensors-heading" variant="h6" component="h2" sx={{mb: 2}}>Sensors</Typography>
            <SensorPanel />
        </Box>
    </Stack>;
}
