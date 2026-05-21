'use client';

import { Box, Typography } from '@mui/material';
import { GREYSCALE } from '@/styles/theme-constants';

/** Inactive tab label — Figma greyscale/text---icon/caption */
const TAB_LABEL_INACTIVE = '#b6bdc9';

export interface DetailTabNavItem {
  key: string;
  label: string;
  id?: string;
  'aria-controls'?: string;
}

export interface DetailTabNavProps {
  tabs: DetailTabNavItem[];
  activeIndex: number;
  onChange: (index: number) => void;
  'aria-label'?: string;
}

/**
 * Detail page tab navigation (Figma Tab_navi_menu 1435:39832).
 * Each tab: 18px bold label; active tab only gets a 3px underline.
 */
export function DetailTabNav({
  tabs,
  activeIndex,
  onChange,
  'aria-label': ariaLabel = 'Detail page tabs',
}: DetailTabNavProps) {
  return (
    <Box
      role="tablist"
      aria-label={ariaLabel}
      sx={{
        display: 'flex',
        gap: '50px',
        alignItems: 'flex-start',
        flexWrap: 'wrap',
      }}
    >
      {tabs.map((tab, index) => {
        const selected = activeIndex === index;
        return (
          <Box
            key={tab.key}
            role="tab"
            id={tab.id}
            aria-selected={selected}
            aria-controls={tab['aria-controls']}
            tabIndex={selected ? 0 : -1}
            component="button"
            type="button"
            onClick={() => onChange(index)}
            sx={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'flex-start',
              gap: '8px',
              py: '5px',
              px: 0,
              border: 'none',
              background: 'transparent',
              cursor: 'pointer',
              outline: 'none',
              minWidth: 0,
              '&:focus-visible': {
                outline: '2px solid',
                outlineColor: 'primary.main',
                outlineOffset: 2,
                borderRadius: '2px',
              },
            }}
          >
            <Typography
              component="span"
              sx={{
                fontSize: 18,
                fontWeight: 700,
                lineHeight: '25px',
                color: selected ? GREYSCALE.light.title : TAB_LABEL_INACTIVE,
                whiteSpace: 'nowrap',
              }}
            >
              {tab.label}
            </Typography>
            {selected ? (
              <Box
                aria-hidden
                sx={{
                  width: '100%',
                  height: '3px',
                  bgcolor: GREYSCALE.light.title,
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
