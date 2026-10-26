'use client';

import * as React from 'react';
import { Box, Typography } from '@mui/material';
import type { SxProps, Theme } from '@mui/material/styles';

export interface DetailTabNavItem {
  key: string;
  label: string;
  /** Rendered beside the label, e.g. a BetaBadge. Kept out of the label's
   * <span>, since Chip renders a <div> and a div inside a span is invalid. */
  badge?: React.ReactNode;
  id?: string;
  'aria-controls'?: string;
}

export interface DetailTabNavProps {
  tabs: DetailTabNavItem[];
  activeIndex: number;
  onChange: (index: number) => void;
  'aria-label'?: string;
  /** Horizontal space between tabs. Default 50px (full-width detail pages). */
  tabGap?: string | number;
  /** Keep tabs on one row with horizontal scroll when they overflow. */
  scrollable?: boolean;
  /** `compact`: 14px labels and a 2px underline that sits on the row's bottom edge, for dense panels. */
  size?: 'default' | 'compact';
  sx?: SxProps<Theme>;
}

/**
 * Detail page tab navigation (Figma Tab_navi_menu 1435:39832).
 * Each tab: 18px bold label; active tab only gets a 3px underline.
 * Keyboard: ArrowLeft/ArrowRight/Home/End move focus per ARIA tablist pattern.
 */
export function DetailTabNav({
  tabs,
  activeIndex,
  onChange,
  'aria-label': ariaLabel = 'Detail page tabs',
  tabGap = '50px',
  scrollable = false,
  size = 'default',
  sx,
}: DetailTabNavProps) {
  const compact = size === 'compact';
  const tabRefs = React.useRef<(HTMLButtonElement | null)[]>([]);

  const handleKeyDown = (e: React.KeyboardEvent, index: number) => {
    let next: number | null = null;
    if (e.key === 'ArrowRight') next = (index + 1) % tabs.length;
    else if (e.key === 'ArrowLeft')
      next = (index - 1 + tabs.length) % tabs.length;
    else if (e.key === 'Home') next = 0;
    else if (e.key === 'End') next = tabs.length - 1;

    if (next !== null) {
      e.preventDefault();
      onChange(next);
      tabRefs.current[next]?.focus();
    }
  };

  return (
    <Box
      role="tablist"
      aria-label={ariaLabel}
      sx={[
        {
          display: 'flex',
          gap: tabGap,
          alignItems: compact ? 'stretch' : 'flex-start',
          flexWrap: scrollable ? 'nowrap' : 'wrap',
          ...(scrollable
            ? {
                overflowX: 'auto',
                overflowY: 'hidden',
                pb: compact ? 0 : '2px',
                scrollbarWidth: 'thin',
              }
            : {}),
        },
        ...(Array.isArray(sx) ? sx : sx ? [sx] : []),
      ]}
    >
      {tabs.map((tab, index) => {
        const selected = activeIndex === index;
        return (
          <Box
            key={tab.key}
            ref={(el: HTMLButtonElement | null) => {
              tabRefs.current[index] = el;
            }}
            role="tab"
            id={tab.id}
            aria-selected={selected}
            aria-controls={tab['aria-controls']}
            tabIndex={selected ? 0 : -1}
            component="button"
            type="button"
            onClick={() => onChange(index)}
            onKeyDown={e => handleKeyDown(e, index)}
            sx={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'flex-start',
              gap: '8px',
              py: '5px',
              px: 0,
              border: 'none',
              ...(compact
                ? {
                    justifyContent: 'center',
                    gap: 0,
                    py: 0,
                    borderBottom: '2px solid',
                    borderBottomColor: selected
                      ? 'greyscale.title'
                      : 'transparent',
                  }
                : {}),
              background: 'transparent',
              cursor: 'pointer',
              outline: 'none',
              minWidth: 0,
              flexShrink: scrollable ? 0 : 1,
              '&:focus-visible': {
                outline: '2px solid',
                outlineColor: 'primary.main',
                outlineOffset: 2,
                borderRadius: '2px',
              },
            }}
          >
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1,
                minWidth: 0,
              }}
            >
              <Typography
                component="span"
                variant={compact ? 'body2' : undefined}
                sx={{
                  ...(compact
                    ? { fontWeight: 600 }
                    : { fontSize: 18, fontWeight: 700, lineHeight: '25px' }),
                  color: theme =>
                    selected
                      ? theme.palette.greyscale.title
                      : theme.palette.greyscale.subtitle,
                  whiteSpace: 'nowrap',
                }}
              >
                {tab.label}
              </Typography>
              {tab.badge}
            </Box>
            {selected && !compact ? (
              <Box
                aria-hidden
                sx={{
                  width: '100%',
                  height: '3px',
                  bgcolor: theme => theme.palette.greyscale.title,
                  flexShrink: 0,
                }}
              />
            ) : null}
          </Box>
        );
      })}
    </Box>
  );
}

export default DetailTabNav;
