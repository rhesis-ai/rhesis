import React from 'react';
import { Box, Typography } from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { BORDER_RADIUS } from '@/styles/theme-constants';

interface EntityInfoBannerProps {
  name: string;
  description?: string | null;
}

/**
 * Figma-aligned info banner for entity detail pages (Figma node 1299:16000).
 * Light-blue background strip with an info icon, entity name (bold 18px, teal)
 * and optional description (regular 16px, teal).
 */
export function EntityInfoBanner({ name, description }: EntityInfoBannerProps) {
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: 1.5,
        bgcolor: '#e5f2ff',
        borderRadius: BORDER_RADIUS.xs,
        px: '30px',
        py: '12px',
      }}
    >
      <InfoOutlinedIcon
        sx={{ fontSize: 22, color: 'primary.main', mt: '3px', flexShrink: 0 }}
      />
      <Box>
        <Typography
          sx={{
            fontWeight: 700,
            fontSize: 18,
            lineHeight: '25px',
            color: 'primary.main',
          }}
        >
          {name}
        </Typography>
        {description && (
          <Typography
            sx={{
              fontWeight: 400,
              fontSize: 16,
              lineHeight: '24px',
              color: 'primary.main',
            }}
          >
            {description}
          </Typography>
        )}
      </Box>
    </Box>
  );
}

export default EntityInfoBanner;
