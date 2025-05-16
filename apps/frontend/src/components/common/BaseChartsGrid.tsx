import React, { ReactNode } from 'react';
import { Grid, Box } from '@mui/material';

export interface BaseChartsGridProps {
  children: ReactNode | ReactNode[];
  spacing?: number;
  columns?: {
    xs?: number;
    sm?: number;
    md?: number;
    lg?: number;
    xl?: number;
  };
  marginBottom?: number;
}

export default function BaseChartsGrid({
  children,
  spacing = 3,
  columns = { xs: 12, md: 3 },
  marginBottom = 4
}: BaseChartsGridProps) {
  return (
    <Grid container spacing={spacing} sx={{ mb: marginBottom }}>
      {React.Children.map(children, (child, index) => (
        <Grid item key={index} {...columns}>
          {child}
        </Grid>
      ))}
    </Grid>
  );
} 