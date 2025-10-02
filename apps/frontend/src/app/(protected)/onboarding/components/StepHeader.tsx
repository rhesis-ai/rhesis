import * as React from 'react';
import { Box, Typography } from '@mui/material';

interface StepHeaderProps {
  title: string;
  description: string;
  subtitle?: string;
}

export default function StepHeader({
  title,
  description,
  subtitle,
}: StepHeaderProps) {
  return (
    <Box textAlign="center" mb={4}>
      <Typography variant="h5" component="h2" gutterBottom color="primary">
        {title}
      </Typography>
      <Typography variant="body1" color="text.secondary">
        {description}
      </Typography>
      {subtitle && (
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
          {subtitle}
        </Typography>
      )}
    </Box>
  );
}
