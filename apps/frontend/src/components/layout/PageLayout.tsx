'use client';

import React from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Link from '@mui/material/Link';
import NextLink from 'next/link';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import { GREYSCALE, FAB_GROUP_GAP } from '@/styles/theme-constants';

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
  /** Optional metadata strip rendered below the description (e.g. "created by / created on") */
  metadata?: React.ReactNode;
  children: React.ReactNode;
}

function PageBreadcrumbs({ items }: { items: BreadcrumbItem[] }) {
  return (
    <Box
      component="nav"
      aria-label="breadcrumb"
      sx={{
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        gap: '10px',
      }}
    >
      {items.map((crumb, idx) => {
        const isLast = idx === items.length - 1;
        const text = crumb.label ?? crumb.title ?? '';
        const link = crumb.href ?? crumb.path;
        const showSeparator = idx < items.length - 1;
        const crumbKey = link ? `${link}|${text}` : text;

        return (
          <Box
            key={crumbKey}
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            {isLast || !link ? (
              <Typography
                variant="bodyMReg"
                component="span"
                sx={{
                  color: theme =>
                    theme.palette.mode === 'light'
                      ? GREYSCALE.light.body
                      : GREYSCALE.dark.body,
                  fontWeight: 400,
                }}
              >
                {text}
              </Typography>
            ) : (
              <Link
                component={NextLink}
                href={link}
                underline="hover"
                sx={{
                  color: theme =>
                    theme.palette.mode === 'light'
                      ? GREYSCALE.light.subtitle
                      : GREYSCALE.dark.subtitle,
                  fontSize: 14,
                  lineHeight: '22px',
                  fontWeight: 400,
                }}
              >
                {text}
              </Link>
            )}
            {showSeparator && (
              <ChevronRightIcon
                sx={{
                  fontSize: 20,
                  color: theme =>
                    theme.palette.mode === 'light'
                      ? GREYSCALE.light.subtitle
                      : GREYSCALE.dark.subtitle,
                }}
                aria-hidden
              />
            )}
          </Box>
        );
      })}
    </Box>
  );
}

/**
 * Standard page header + content wrapper.
 * Matches Figma Top 841:38534 and Section Text 841:38539.
 */
export function PageLayout({
  title,
  description,
  breadcrumbs,
  actions,
  metadata,
  children,
}: PageLayoutProps) {
  const crumbItems =
    breadcrumbs?.filter(b => (b.label ?? b.title)?.trim()) ?? [];
  const hasBreadcrumbs = crumbItems.length > 0;
  const hasHeader = hasBreadcrumbs || title || description || actions;

  return (
    <Box sx={{ width: '100%' }}>
      {hasHeader && (
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            gap: '20px',
            mb: 5,
          }}
        >
          {hasBreadcrumbs && <PageBreadcrumbs items={crumbItems} />}

          {(title || description || actions || metadata) && (
            <Box
              sx={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'flex-start',
                width: '100%',
              }}
            >
              {(title || actions) && (
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: '16px',
                    width: '100%',
                    minHeight: 56,
                  }}
                >
                  {title && (
                    <Typography
                      variant="h4"
                      component="h1"
                      sx={{
                        flex: '1 1 0',
                        minWidth: 0,
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
                        gap: FAB_GROUP_GAP,
                        flexShrink: 0,
                        alignItems: 'center',
                      }}
                    >
                      {actions}
                    </Box>
                  )}
                </Box>
              )}

              {description && (
                <Typography
                  variant="bodyLReg"
                  component="p"
                  sx={{
                    mt: title || actions ? 0 : 0,
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

              {metadata && (
                <Box sx={{ mt: description ? 1.5 : 0, width: '100%' }}>
                  {metadata}
                </Box>
              )}
            </Box>
          )}
        </Box>
      )}

      {children}
    </Box>
  );
}

export default PageLayout;
