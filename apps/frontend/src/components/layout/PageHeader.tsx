'use client';

import React from 'react';
import {
  Box,
  Typography,
  Breadcrumbs as MuiBreadcrumbs,
  Link as MuiLink,
} from '@mui/material';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import NextLink from 'next/link';

export interface BreadcrumbItem {
  label: string;
  href?: string;
}

interface PageHeaderProps {
  title: string;
  description?: string;
  breadcrumbs?: BreadcrumbItem[];
  actions?: React.ReactNode;
}

export default function PageHeader({
  title,
  description,
  breadcrumbs,
  actions,
}: PageHeaderProps) {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        gap: 2.5,
        px: 4,
        pt: 3,
        pb: 0,
      }}
    >
      {/* Breadcrumbs row — gap: 10px between items */}
      {breadcrumbs && breadcrumbs.length > 0 && (
        <MuiBreadcrumbs
          separator={
            <ChevronRightIcon sx={{ fontSize: 20, color: 'grey.500' }} />
          }
          sx={{
            '& .MuiBreadcrumbs-separator': { mx: 0.25 },
          }}
        >
          {breadcrumbs.map((crumb, index) => {
            const isLast = index === breadcrumbs.length - 1;
            if (isLast || !crumb.href) {
              return (
                <Typography
                  key={crumb.label}
                  sx={{
                    fontSize: 14,
                    lineHeight: '22px',
                    fontWeight: 400,
                    color: isLast ? 'text.secondary' : 'grey.500',
                  }}
                >
                  {crumb.label}
                </Typography>
              );
            }
            return (
              <MuiLink
                key={crumb.label}
                component={NextLink}
                href={crumb.href}
                underline="hover"
                sx={{
                  fontSize: 14,
                  lineHeight: '22px',
                  fontWeight: 400,
                  color: 'grey.500',
                }}
              >
                {crumb.label}
              </MuiLink>
            );
          })}
        </MuiBreadcrumbs>
      )}

      {/* Section Text: title row + description (no gap between them) */}
      <Box sx={{ display: 'flex', flexDirection: 'column' }}>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 2,
            width: '100%',
          }}
        >
          <Typography
            sx={{
              fontSize: 28,
              fontWeight: 700,
              lineHeight: '33.6px',
              color: 'text.primary',
              flex: 1,
              minWidth: 0,
            }}
          >
            {title}
          </Typography>
          {actions && (
            <Box
              sx={{
                display: 'flex',
                gap: 2.5,
                flexShrink: 0,
                alignItems: 'center',
              }}
            >
              {actions}
            </Box>
          )}
        </Box>

        {description && (
          <Typography
            sx={{
              fontSize: 16,
              fontWeight: 400,
              lineHeight: '24px',
              color: 'text.secondary',
              maxWidth: 800,
            }}
          >
            {description}
          </Typography>
        )}
      </Box>
    </Box>
  );
}
