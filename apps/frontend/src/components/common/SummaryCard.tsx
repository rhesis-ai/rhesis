'use client';

import React from 'react';
import { Box, Card, CardContent, Typography, useTheme } from '@mui/material';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';

export interface SummaryCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ReactNode;
  trend?: 'up' | 'down' | 'neutral';
  trendValue?: string;
  color?: 'primary' | 'success' | 'error' | 'warning' | 'info';
}

/**
 * Headline stat tile: a label, one big number, and a line saying what the
 * number is out of. Used by the test run header and the metric tuning tab.
 */
export function SummaryCard({
  title,
  value,
  subtitle,
  icon,
  trend,
  trendValue,
  color = 'primary',
}: SummaryCardProps) {
  const theme = useTheme();

  const iconColors = {
    primary: theme.palette.primary.main,
    success: theme.palette.success.main,
    error: theme.palette.error.main,
    warning: theme.palette.warning.main,
    info: theme.palette.info.main,
  };

  return (
    <Card
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <CardContent sx={{ flexGrow: 1, p: 3 }}>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
            mb: 2,
          }}
        >
          <Typography variant="body2" color="text.secondary" fontWeight={500}>
            {title}
          </Typography>
          <Box
            sx={{
              color: iconColors[color],
              display: 'flex',
              alignItems: 'center',
            }}
          >
            {icon}
          </Box>
        </Box>

        <Typography variant="h4" fontWeight={600} sx={{ mb: 1 }}>
          {value}
        </Typography>

        {subtitle && (
          <Typography variant="body2" color="text.secondary">
            {subtitle}
          </Typography>
        )}

        {trend && trendValue && (
          <Box sx={{ display: 'flex', alignItems: 'center', mt: 1, gap: 0.5 }}>
            {trend === 'up' && (
              <TrendingUpIcon fontSize="small" color="success" />
            )}
            {trend === 'down' && (
              <TrendingDownIcon fontSize="small" color="error" />
            )}
            <Typography
              variant="caption"
              color={
                trend === 'up'
                  ? 'success.main'
                  : trend === 'down'
                    ? 'error.main'
                    : 'text.secondary'
              }
              fontWeight={500}
            >
              {trendValue}
            </Typography>
          </Box>
        )}
      </CardContent>
    </Card>
  );
}

export default SummaryCard;
