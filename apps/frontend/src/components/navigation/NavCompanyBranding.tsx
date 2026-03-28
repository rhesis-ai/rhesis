'use client';

import React from 'react';
import { Box, Typography, Tooltip } from '@mui/material';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import Image from 'next/image';

export interface NavCompanyBrandingProps {
  mini?: boolean;
  onClick?: (event: React.MouseEvent<HTMLElement>) => void;
}

export default function NavCompanyBranding({
  mini = false,
  onClick,
}: NavCompanyBrandingProps) {
  if (mini) {
    return (
      <Tooltip title="Rhesis AI" placement="right">
        <Box
          onClick={onClick}
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            py: 1.5,
            px: 1,
            cursor: onClick ? 'pointer' : 'default',
          }}
        >
          <Image
            src="/logos/rhesis-logo-favicon-transparent.svg"
            alt="Rhesis AI"
            width={40}
            height={40}
            priority
          />
        </Box>
      </Tooltip>
    );
  }

  return (
    <Box
      onClick={onClick}
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 1,
        cursor: onClick ? 'pointer' : 'default',
        '&:hover': onClick
          ? { bgcolor: 'grey.200', borderRadius: 1 }
          : undefined,
      }}
    >
      <Image
        src="/logos/rhesis-logo-favicon-transparent.svg"
        alt="Rhesis AI"
        width={40}
        height={40}
        priority
      />
      <Typography
        sx={{
          fontSize: 16,
          fontWeight: 700,
          lineHeight: '24px',
          color: 'text.primary',
          whiteSpace: 'nowrap',
        }}
      >
        Rhesis AI
      </Typography>
      {onClick && (
        <KeyboardArrowDownIcon sx={{ fontSize: 24, color: 'text.primary' }} />
      )}
    </Box>
  );
}
