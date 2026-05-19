'use client';

import React from 'react';
import { useTheme } from '@mui/material/styles';
import { Box, Typography, Avatar, IconButton } from '@mui/material';
import { DeleteIcon } from '@/components/icons';
import { GREYSCALE, BORDER_RADIUS, ELEVATION } from '@/styles/theme';

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
}

export interface EntityCardProps {
  icon: React.ReactNode;
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

// Status dot / badge colours — intentional semantic values, defined once here
const STATUS_COLORS: Record<string, string> = {
  active: '#38ad87', // Intentional: semantic green
  inactive: '#ef4444', // Intentional: semantic red
};

function getStatusColor(status: string): string {
  return STATUS_COLORS[status.toLowerCase()] ?? GREYSCALE.light.subtitle;
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

  const statusColor = status ? getStatusColor(status) : null;
  const statusLabel = status
    ? status.charAt(0).toUpperCase() + status.slice(1).toLowerCase()
    : null;

  const hasChipContent = !!(chipSections && chipSections.length > 0);
  const hasFurtherInfo = !!status || hasChipContent;

  const isDark = theme.palette.mode === 'dark';
  const defaultBorderColor = isDark
    ? theme.palette.divider
    : GREYSCALE.light.border;
  const resolvedBorderColor = borderColorProp ?? defaultBorderColor;
  const chipBg = isDark ? GREYSCALE.dark.surface2 : GREYSCALE.light.surface2;

  return (
    <Box
      onClick={onClick}
      sx={{
        bgcolor: 'background.paper',
        border: `1px solid ${resolvedBorderColor}`,
        borderRadius: BORDER_RADIUS.md,
        p: '30px',
        boxShadow: ELEVATION.xs,
        position: 'relative',
        display: 'flex',
        flexDirection: 'column',
        gap: '20px',
        cursor: onClick ? 'pointer' : 'default',
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
        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
          <Box
            sx={{
              width: 24,
              height: 24,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'primary.dark',
              flexShrink: 0,
              '& .MuiSvgIcon-root': { fontSize: 20 },
            }}
          >
            {icon}
          </Box>
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

        {/* Description — clamped to 3 lines so cards share equal height */}
        {description && (
          <Typography
            sx={{
              fontSize: 14,
              fontWeight: 400,
              lineHeight: '22px',
              color: 'text.secondary',
              display: '-webkit-box',
              WebkitLineClamp: 3,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
            }}
          >
            {description}
          </Typography>
        )}
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
          {/* Status badge */}
          {statusColor && statusLabel && (
            <Box sx={{ display: 'flex' }}>
              <Box
                sx={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px',
                  border: `1px solid ${statusColor}`,
                  borderRadius: BORDER_RADIUS.pill,
                  px: '10px',
                  py: '2px',
                }}
              >
                <Box
                  sx={{
                    width: 6,
                    height: 6,
                    borderRadius: BORDER_RADIUS.pill,
                    bgcolor: statusColor,
                    flexShrink: 0,
                  }}
                />
                <Typography
                  sx={{ fontSize: 12, color: statusColor, lineHeight: 1.5 }}
                >
                  {statusLabel}
                </Typography>
              </Box>
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
                      color: GREYSCALE.light.subtitle,
                      textTransform: 'uppercase',
                      letterSpacing: '0.04em',
                      lineHeight: '18px',
                      fontWeight: 400,
                    }}
                  >
                    {section.label}
                  </Typography>
                )}

                {section.chips.length > 0 ? (
                  <Box sx={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                    {section.chips.map(chip => (
                      <Box
                        key={chip.key}
                        sx={{
                          bgcolor: chipBg,
                          borderRadius: '4px',
                          px: '10px',
                          pt: '1px',
                          pb: '2px',
                          fontSize: 12,
                          color: 'text.secondary',
                          lineHeight: '18px',
                          ...(chip.maxWidth && {
                            maxWidth: chip.maxWidth,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }),
                        }}
                      >
                        {chip.label}
                      </Box>
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
    </Box>
  );
}
