'use client';

import React from 'react';
import { useTheme } from '@mui/material/styles';
import { Box, ButtonBase, Typography, Avatar, IconButton } from '@mui/material';
import { DeleteIcon } from '@/components/icons';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme';
import GridBadge from '@/components/common/GridBadge';

export interface ChipData {
  key: string;
  label: string;
  icon?: React.ReactNode;
  variant?: 'filled' | 'outlined';
  maxWidth?: string | number;
  tooltip?: string;
}

export interface ChipSection {
  label?: string;
  chips: ChipData[];
  emptyText?: string;
  /** Renders instead of chips when set (e.g. status badge on project cards). */
  customContent?: React.ReactNode;
}

export interface EntityCardProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  onClick?: () => void;
  onDelete?: () => void;
  userAvatar?: string;
  userName?: string;
  status?: 'active' | 'inactive' | string;
  chipSections?: ChipSection[];
  topRightActions?: React.ReactNode;
  captionText?: string;
  /** Overrides the default card border color (e.g. 'warning.main' for validation errors) */
  borderColor?: string;
  /** Optional content rendered inside the card after chip sections */
  footer?: React.ReactNode;
}

// Status chip colours — Figma Chip with semantic green/red tint
const STATUS_CHIP_STYLES: Record<string, { bg: string; color: string }> = {
  active: { bg: 'rgba(56, 173, 135, 0.14)', color: '#38ad87' },
  inactive: { bg: 'rgba(239, 68, 68, 0.12)', color: '#ef4444' },
};

/** Figma greyscale/surface/default — matches linked-entity chips */
const CHIP_SURFACE_DEFAULT = '#f3f4f6';

function getStatusChipStyles(
  status: string,
  isDark: boolean
): { bg: string; color: string } {
  const preset = STATUS_CHIP_STYLES[status.toLowerCase()];
  if (preset) {
    return preset;
  }
  return {
    bg: isDark ? '#0d1117' : CHIP_SURFACE_DEFAULT,
    color: isDark ? '#c9d1d9' : '#2a2e36',
  };
}

const DESCRIPTION_FONT_SIZE = 14;
const DESCRIPTION_LINE_HEIGHT = 22;
const DESCRIPTION_MAX_LINES = 3;
const DESCRIPTION_MIN_HEIGHT = DESCRIPTION_LINE_HEIGHT * DESCRIPTION_MAX_LINES;

/** Status badge on entity cards — pill shape; semantic tint for active/inactive. */
export function EntityCardStatusBadge({ status }: { status: string }) {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const { bg, color } = getStatusChipStyles(status, isDark);
  const statusLabel =
    status.charAt(0).toUpperCase() + status.slice(1).toLowerCase();

  return (
    <GridBadge
      size="detail"
      label={statusLabel}
      sx={{
        alignSelf: 'flex-start',
        bgcolor: bg,
        color,
      }}
    />
  );
}

export default function EntityCard({
  icon,
  title,
  description,
  onClick,
  onDelete,
  userAvatar,
  userName,
  status,
  chipSections,
  topRightActions,
  captionText,
  borderColor: borderColorProp,
  footer,
}: EntityCardProps) {
  const theme = useTheme();

  const firstName = userName
    ? userName.split(' ')[0]
    : (captionText ?? undefined);
  const hasTopRightContent = !!topRightActions || !!onDelete;

  const hasChipContent = !!(chipSections && chipSections.length > 0);
  const hasFurtherInfo = !!status || hasChipContent;

  const isDark = theme.palette.mode === 'dark';
  const defaultBorderColor = isDark
    ? theme.palette.divider
    : theme.palette.greyscale.border;
  const resolvedBorderColor = borderColorProp ?? defaultBorderColor;
  return (
    <ButtonBase
      component="div"
      onClick={onClick}
      tabIndex={onClick ? 0 : -1}
      disableRipple={!onClick}
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'stretch',
        textAlign: 'left',
        bgcolor: 'background.paper',
        border: `1px solid ${resolvedBorderColor}`,
        borderRadius: BORDER_RADIUS.md,
        p: '30px',
        boxShadow: ELEVATION.xs,
        position: 'relative',
        gap: '20px',
        cursor: onClick ? 'pointer' : 'inherit',
        height: '100%',
        boxSizing: 'border-box',
        transition: 'box-shadow 0.2s ease',
        '&:hover': onClick
          ? { boxShadow: '0px 6px 16px rgba(0,0,0,0.14)' }
          : {},
      }}
    >
      {/* Top-right actions */}
      {hasTopRightContent && (
        <Box
          sx={{
            position: 'absolute',
            top: '14px',
            right: '14px',
            display: 'flex',
            alignItems: 'center',
            gap: '2px',
            zIndex: 1,
          }}
          onClick={e => e.stopPropagation()}
        >
          {topRightActions}
          {onDelete && (
            <IconButton
              size="small"
              onClick={e => {
                e.stopPropagation();
                onDelete();
              }}
              sx={{
                color: 'primary.dark',
                padding: '2px',
                '& .MuiSvgIcon-root': { fontSize: 20 },
              }}
            >
              <DeleteIcon />
            </IconButton>
          )}
        </Box>
      )}

      {/* Header section */}
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {/* Icon + Title row */}
        <Box
          sx={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: icon ? '10px' : 0,
          }}
        >
          {icon && (
            <Box
              sx={{
                width: 24,
                height: 24,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'text.primary',
                flexShrink: 0,
                '& .MuiSvgIcon-root': { fontSize: 20 },
              }}
            >
              {icon}
            </Box>
          )}
          <Typography
            sx={{
              fontSize: 18,
              fontWeight: 700,
              lineHeight: '25px',
              color: 'text.primary',
              wordBreak: 'break-word',
              flex: 1,
              pr: hasTopRightContent ? '36px' : 0,
            }}
          >
            {title}
          </Typography>
        </Box>

        {/* Description — always reserves 3 lines so card footers align */}
        <Typography
          data-testid="entity-card-description"
          sx={{
            fontSize: DESCRIPTION_FONT_SIZE,
            fontWeight: 400,
            lineHeight: `${DESCRIPTION_LINE_HEIGHT}px`,
            minHeight: `${DESCRIPTION_MIN_HEIGHT}px`,
            color: 'text.secondary',
            display: '-webkit-box',
            WebkitLineClamp: DESCRIPTION_MAX_LINES,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
          }}
        >
          {description ?? ''}
        </Typography>
      </Box>

      {/* User row */}
      {firstName && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
          <Avatar src={userAvatar} sx={{ width: 24, height: 24, fontSize: 11 }}>
            {!userAvatar && firstName ? firstName[0].toUpperCase() : undefined}
          </Avatar>
          <Typography
            sx={{ fontSize: 12, fontWeight: 400, color: 'text.secondary' }}
          >
            {firstName}
          </Typography>
        </Box>
      )}

      {/* Further info section */}
      {hasFurtherInfo && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
          {/* Status chip — shown above divider when not placed in a chip section */}
          {status && (
            <Box sx={{ display: 'flex', alignItems: 'flex-start' }}>
              <EntityCardStatusBadge status={status} />
            </Box>
          )}

          {/* Divider — separates status/user info from chip sections */}
          {hasChipContent && (
            <Box
              sx={{
                height: '1px',
                bgcolor: resolvedBorderColor,
                width: '100%',
              }}
            />
          )}

          {/* Chip sections */}
          {hasChipContent &&
            chipSections?.map((section, idx) => (
              <Box
                key={section.label ?? `section-${idx}`}
                sx={{ display: 'flex', flexDirection: 'column', gap: '6px' }}
              >
                {section.label && (
                  <Typography
                    sx={{
                      fontSize: 12,
                      color: theme => theme.palette.greyscale.subtitle,
                      textTransform: 'uppercase',
                      letterSpacing: '0.04em',
                      lineHeight: '18px',
                      fontWeight: 400,
                    }}
                  >
                    {section.label}
                  </Typography>
                )}

                {section.customContent ? (
                  <Box sx={{ display: 'flex', alignItems: 'flex-start' }}>
                    {section.customContent}
                  </Box>
                ) : section.chips.length > 0 ? (
                  <Box sx={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                    {section.chips.map(chip => (
                      <GridBadge
                        size="detail"
                        key={chip.key}
                        label={chip.label}
                        sx={
                          chip.maxWidth
                            ? {
                                maxWidth: chip.maxWidth,
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                              }
                            : undefined
                        }
                      />
                    ))}
                  </Box>
                ) : (
                  <Typography
                    sx={{
                      fontSize: 12,
                      fontWeight: 400,
                      color: 'text.secondary',
                    }}
                  >
                    {section.emptyText ?? 'No entity assigned yet'}
                  </Typography>
                )}
              </Box>
            ))}
        </Box>
      )}

      {/* Footer slot — model-specific content (status chip, action buttons) */}
      {footer && <Box>{footer}</Box>}
    </ButtonBase>
  );
}
