import React from 'react';
import { Grid } from '@mui/material';
import styles from '@/styles/BaseChartsGrid.module.css';

export interface BaseChartsGridProps {
  children: React.ReactNode;
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
  marginBottom = 4,
}: BaseChartsGridProps) {
  // Set the CSS variable for grid margin
  const gridStyle = {
    '--grid-margin': `${marginBottom * 8}px`,
  } as React.CSSProperties;

  return (
    <Grid container spacing={spacing} className={styles.grid} style={gridStyle}>
      {React.Children.map(children, (child, index) => {
        // Generate a stable key from child type and index
        const childKey = React.isValidElement(child)
          ? `${child.type?.toString().split(' ')[1] || 'child'}-${index}`
          : `child-${index}`;
        return (
          <Grid key={childKey} size={columns}>
            {child}
          </Grid>
        );
      })}
    </Grid>
  );
}
