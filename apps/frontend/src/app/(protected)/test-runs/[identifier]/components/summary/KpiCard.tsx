'use client';

import React from 'react';
import {
  Box,
  Card,
  CardActionArea,
  CardContent,
  Tooltip,
  Typography,
} from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { INLINE_ICON_SIZE } from './summary-tokens';

interface KpiCardProps {
  title: string;
  value: string | number;
  /** Rendered smaller and muted right after value, e.g. "/ 38" or "%". */
  valueSuffix?: string;
  /** Theme color path for the value, e.g. 'error.main' when failures > 0. */
  valueColor?: string;
  /** Plain text, or a node when part of it needs its own styling (e.g. a red
   *  failures count inline with the rest of the sentence). */
  subtitle?: React.ReactNode;
  /** Rendered between the value and the subtitle -- a progress bar or a
   *  compact sparkline strip. */
  visual?: React.ReactNode;
  /** Explains the metric in a hover tooltip via a small info icon next to the title. */
  infoTooltip?: string;
  /** A second metric of equal standing, shown beside `value`. Both drop a size so
   *  the pair still fits the card width. Used by the Usage card, where tokens and
   *  cost answer the same question and neither is the subtitle of the other. */
  secondary?: { value: string | number; label: string };
  /** Labels the primary value when `secondary` is set, so the two read as a pair. */
  valueLabel?: string;
  /** Makes the whole card a button, e.g. to drill into a filtered view. */
  onClick?: () => void;
}

export default function KpiCard({
  title,
  value,
  valueSuffix,
  valueColor,
  subtitle,
  visual,
  infoTooltip,
  secondary,
  valueLabel,
  onClick,
}: KpiCardProps) {
  const content = (
    <CardContent sx={{ flexGrow: 1, p: 3 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 2 }}>
        <Typography variant="body2" color="text.secondary" fontWeight={500}>
          {title}
        </Typography>
        {infoTooltip && (
          <Tooltip title={infoTooltip} placement="top" arrow>
            <InfoOutlinedIcon
              sx={{ fontSize: INLINE_ICON_SIZE, color: 'text.secondary' }}
            />
          </Tooltip>
        )}
      </Box>

      {secondary ? (
        <Box sx={{ display: 'flex', gap: 3, mb: 1 }}>
          <Box>
            <Typography
              variant="h5"
              fontWeight={600}
              sx={{ fontVariantNumeric: 'tabular-nums', color: valueColor }}
            >
              {value}
            </Typography>
            {valueLabel && (
              <Typography variant="caption" color="text.secondary">
                {valueLabel}
              </Typography>
            )}
          </Box>
          <Box>
            <Typography
              variant="h5"
              fontWeight={600}
              sx={{ fontVariantNumeric: 'tabular-nums' }}
            >
              {secondary.value}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {secondary.label}
            </Typography>
          </Box>
        </Box>
      ) : (
        <Typography
          variant="h4"
          fontWeight={600}
          sx={{
            mb: 1,
            fontVariantNumeric: 'tabular-nums',
            color: valueColor,
          }}
        >
          {value}
          {valueSuffix && (
            <Typography
              component="span"
              variant="body1"
              color="text.secondary"
              sx={{ ml: 0.5, fontVariantNumeric: 'tabular-nums' }}
            >
              {valueSuffix}
            </Typography>
          )}
        </Typography>
      )}

      {visual}

      {subtitle && (
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
          {subtitle}
        </Typography>
      )}
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
          sx={{
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'stretch',
            justifyContent: 'flex-start',
          }}
        >
          {content}
        </CardActionArea>
      ) : (
        content
      )}
    </Card>
  );
}
