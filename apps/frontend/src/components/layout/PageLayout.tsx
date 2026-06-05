'use client';

import React from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Link from '@mui/material/Link';
import NextLink from 'next/link';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import { FAB_GROUP_GAP } from '@/styles/theme-constants';

export interface BreadcrumbItem {
  /** Display text for the breadcrumb. */
  label: string;
  /** Navigation target (omit for the current/last crumb). */
  href?: string;
}

export interface PageLayoutProps {
  title?: string | React.ReactNode;
  description?: string;
  breadcrumbs?: BreadcrumbItem[];
  /** Actions rendered top-right (e.g. FAB cluster) */
  actions?: React.ReactNode;
  /** Optional metadata strip rendered below the description (e.g. "created by / created on") */
  metadata?: React.ReactNode;
  children: React.ReactNode;
  /** When true the layout grows to fill the available flex height so child screens
   *  can pin a bottom ActionBar to the viewport edge without magic numbers. */
  fullHeight?: boolean;
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
        const text = crumb.label;
        const link = crumb.href;
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
                  color: theme => theme.palette.greyscale.body,
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
                  color: theme => theme.palette.greyscale.subtitle,
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
                  color: theme => theme.palette.greyscale.subtitle,
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
  fullHeight = false,
}: PageLayoutProps) {
  const crumbItems = breadcrumbs?.filter(b => b.label?.trim()) ?? [];
  const hasBreadcrumbs = crumbItems.length > 0;
  const hasHeader = hasBreadcrumbs || title || description || actions;

  return (
    <Box
      sx={{
        width: '100%',
        ...(fullHeight && {
          display: 'flex',
          flexDirection: 'column',
          flexGrow: 1,
          minHeight: 0,
        }),
      }}
    >
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
                        color: theme => theme.palette.greyscale.title,
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
                        overflow: 'visible',
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
                    color: theme => theme.palette.greyscale.body,
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

      {fullHeight ? (
        <Box
          sx={{
            flex: 1,
            minHeight: 0,
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          {children}
        </Box>
      ) : (
        children
      )}
    </Box>
  );
}

export default PageLayout;
