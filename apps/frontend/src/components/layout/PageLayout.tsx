'use client';

import React from 'react';
import Box from '@mui/material/Box';
import Breadcrumbs from '@mui/material/Breadcrumbs';
import Typography from '@mui/material/Typography';
import Link from '@mui/material/Link';
import NextLink from 'next/link';
import NavigateNextIcon from '@mui/icons-material/NavigateNext';
import { GREYSCALE } from '@/styles/theme';

export interface BreadcrumbItem {
  /** Display text (use `label` for new code; `title` accepted for Toolpad migration compat) */
  label?: string;
  title?: string;
  /** Navigation target (`href` preferred; `path` accepted for Toolpad migration compat) */
  href?: string;
  path?: string;
}

export interface PageLayoutProps {
  title?: string;
  description?: string;
  breadcrumbs?: BreadcrumbItem[];
  /** Actions rendered top-right (e.g. FAB cluster) */
  actions?: React.ReactNode;
  /** Optional metadata strip rendered below the title row (e.g. "created by / created on") */
  metadata?: React.ReactNode;
  children: React.ReactNode;
}

/**
 * Standard page header + content wrapper.
 * Matches the Figma page header pattern (Top 841:38534, Section Text 841:38539):
 *
 *   [Breadcrumbs]                    (20px gap)
 *   [H4 Title + Actions]             (56px min row height)
 *   [Body L description]             (16px gap below title row)
 *
 *   [Content]
 */
export function PageLayout({
  title,
  description,
  breadcrumbs,
  actions,
  metadata,
  children,
}: PageLayoutProps) {
  const hasBreadcrumbs =
    breadcrumbs &&
    breadcrumbs.length > 0 &&
    breadcrumbs.some(b => b.label ?? b.title);

  return (
    <Box sx={{ width: '100%' }}>
      {/* Page header */}
      {(hasBreadcrumbs || title || description || actions) && (
        <Box sx={{ mb: 5 }}>
          {/* Row 0: Breadcrumbs (only when present) */}
          {hasBreadcrumbs && (
            <Breadcrumbs
              separator={
                <NavigateNextIcon
                  sx={{
                    fontSize: 16,
                    color: theme =>
                      theme.palette.mode === 'light'
                        ? GREYSCALE.light.subtitle
                        : GREYSCALE.dark.subtitle,
                  }}
                />
              }
              aria-label="breadcrumb"
              sx={{ mb: 2.5 }}
            >
              {breadcrumbs.map((crumb, idx) => {
                const isLast = idx === breadcrumbs.length - 1;
                const text = crumb.label ?? crumb.title ?? '';
                const link = crumb.href ?? crumb.path;
                if (isLast || !link) {
                  return (
                    <Typography
                      key={text}
                      variant="bodyMReg"
                      sx={{
                        color: isLast
                          ? theme =>
                              theme.palette.mode === 'light'
                                ? GREYSCALE.light.body
                                : GREYSCALE.dark.body
                          : theme =>
                              theme.palette.mode === 'light'
                                ? GREYSCALE.light.subtitle
                                : GREYSCALE.dark.subtitle,
                        fontWeight: isLast ? 500 : 400,
                      }}
                    >
                      {text}
                    </Typography>
                  );
                }
                return (
                  <Link
                    key={text}
                    component={NextLink}
                    href={link}
                    underline="hover"
                    sx={{
                      color: theme =>
                        theme.palette.mode === 'light'
                          ? GREYSCALE.light.subtitle
                          : GREYSCALE.dark.subtitle,
                      fontWeight: 400,
                    }}
                  >
                    {text}
                  </Link>
                );
              })}
            </Breadcrumbs>
          )}

          {/* Row 1: Title (left) + Actions (right) — Figma HL row is 56px tall */}
          {(title || actions) && (
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 2,
                width: '100%',
                minHeight: 56,
              }}
            >
              {title && (
                <Typography
                  variant="h4"
                  component="h1"
                  sx={{
                    color: theme =>
                      theme.palette.mode === 'light'
                        ? GREYSCALE.light.title
                        : GREYSCALE.dark.title,
                  }}
                >
                  {title}
                </Typography>
              )}
              {actions && (
                <Box
                  sx={{
                    display: 'flex',
                    gap: 2,
                    flexShrink: 0,
                    alignItems: 'center',
                  }}
                >
                  {actions}
                </Box>
              )}
            </Box>
          )}

          {/* Row 2: Metadata strip */}
          {metadata && <Box sx={{ mt: 1 }}>{metadata}</Box>}

          {/* Row 3: Description — 16px below title row (Figma Section Text spacing) */}
          {description && (
            <Typography
              variant="bodyLReg"
              sx={{
                mt: 2,
                maxWidth: 800,
                color: theme =>
                  theme.palette.mode === 'light'
                    ? GREYSCALE.light.body
                    : GREYSCALE.dark.body,
              }}
            >
              {description}
            </Typography>
          )}
        </Box>
      )}

      {/* Page content */}
      {children}
    </Box>
  );
}

export default PageLayout;
