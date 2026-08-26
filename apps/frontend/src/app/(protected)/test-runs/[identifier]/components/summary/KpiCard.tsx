'use client';

import React from 'react';
import {
  Box,
  Card,
  CardActionArea,
  CardContent,
  Tooltip,
  Typography,
  useTheme,
} from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';

interface KpiCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: React.ReactNode;
  trend?: React.ReactNode;
  /** Explains the metric in a hover tooltip via a small info icon next to the title. */
  infoTooltip?: string;
  /** Makes the whole card a button, e.g. to drill into a filtered view. */
  onClick?: () => void;
}

export default function KpiCard({
  title,
  value,
  subtitle,
  icon,
  trend,
  infoTooltip,
  onClick,
}: KpiCardProps) {
  const theme = useTheme();

  const content = (
    <CardContent sx={{ flexGrow: 1, p: 3 }}>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          mb: 2,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <Typography variant="body2" color="text.secondary" fontWeight={500}>
            {title}
          </Typography>
          {infoTooltip && (
            <Tooltip title={infoTooltip} placement="top" arrow>
              <InfoOutlinedIcon
                sx={{ fontSize: 14, color: 'text.secondary' }}
              />
            </Tooltip>
          )}
        </Box>
        {icon && (
          <Box
            sx={{
              color: theme.palette.primary.main,
              display: 'flex',
              alignItems: 'center',
            }}
          >
            {icon}
          </Box>
        )}
      </Box>

      <Typography
        variant="h4"
        fontWeight={600}
        sx={{ mb: 1, fontVariantNumeric: 'tabular-nums' }}
      >
        {value}
      </Typography>

      {subtitle && (
        <Typography variant="body2" color="text.secondary">
          {subtitle}
        </Typography>
      )}

      {trend}
    </CardContent>
  );

  return (
    <Card
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {onClick ? (
        <CardActionArea
          onClick={onClick}
          sx={{ height: '100%', alignItems: 'stretch' }}
        >
          {content}
        </CardActionArea>
      ) : (
        content
      )}
    </Card>
  );
}
