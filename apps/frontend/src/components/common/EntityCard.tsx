import React from 'react';
import { useTheme, type Theme } from '@mui/material/styles';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Chip,
  Avatar,
  IconButton,
  Tooltip,
} from '@mui/material';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import FiberManualRecordIcon from '@mui/icons-material/FiberManualRecord';

export interface ChipData {
  key: string;
  icon?: React.ReactNode;
  label: string;
  variant?: 'filled' | 'outlined';
  maxWidth?: string | number | ((theme: Theme) => string | number);
  tooltip?: string;
}

export interface ChipSection {
  label?: string;
  chips: ChipData[];
}

type StatusColor = 'success' | 'warning' | 'error' | 'info' | 'default';

interface EntityCardProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  onClick?: () => void;
  onDelete?: (e: React.MouseEvent) => void;
  ownerName?: string;
  ownerAvatar?: string;
  statusLabel?: string;
  statusColor?: StatusColor;
  chipSections: ChipSection[];
}

const STATUS_COLOR_MAP: Record<StatusColor, string> = {
  success: 'success.main',
  warning: 'warning.main',
  error: 'error.main',
  info: 'info.main',
  default: 'text.secondary',
};

export default function EntityCard({
  icon,
  title,
  description,
  onClick,
  onDelete,
  ownerName,
  ownerAvatar,
  statusLabel,
  statusColor = 'success',
  chipSections,
}: EntityCardProps) {
  const theme = useTheme();

  const hasFooter = chipSections.some(s => s.chips.length > 0);

  return (
    <Card
      onClick={onClick}
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        position: 'relative',
        border: 1,
        borderColor: theme.greyscale.border.disabled,
        ...(onClick && {
          cursor: 'pointer',
          transition: 'box-shadow 0.2s ease-in-out, transform 0.2s ease-in-out',
          '&:hover': {
            boxShadow: theme.shadows[4],
            transform: 'translateY(-2px)',
          },
        }),
      }}
    >
      {onDelete && (
        <Box
          sx={{
            position: 'absolute',
            top: theme.spacing(1.5),
            right: theme.spacing(1.5),
            zIndex: 1,
          }}
        >
          <Tooltip title="Delete">
            <IconButton
              size="small"
              onClick={e => {
                e.stopPropagation();
                onDelete(e);
              }}
              sx={{
                color: 'text.secondary',
                '&:hover': { color: 'error.main' },
              }}
            >
              <DeleteOutlineIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      )}

      <CardContent
        sx={{
          flexGrow: 1,
          display: 'flex',
          flexDirection: 'column',
          p: 3.75,
          '&:last-child': { pb: 3.75 },
        }}
      >
        {/* Header: Icon + Title */}
        <Box
          sx={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: 1.25,
            mb: 1.25,
          }}
        >
          <Box
            sx={{
              color: 'text.secondary',
              display: 'flex',
              alignItems: 'center',
              flexShrink: 0,
              mt: 0.25,
            }}
          >
            {icon}
          </Box>
          <Typography
            variant="subtitle1"
            component="div"
            sx={{
              fontWeight: 700,
              lineHeight: 1.5,
              wordWrap: 'break-word',
              overflowWrap: 'break-word',
              flex: 1,
              pr: onDelete ? 4 : 0,
            }}
          >
            {title}
          </Typography>
        </Box>

        {/* Description */}
        <Typography
          variant="body2"
          sx={{
            color: theme.greyscale.text.body,
            lineHeight: 1.57,
            mb: 2.5,
            minHeight: '2.5em',
            display: '-webkit-box',
            WebkitLineClamp: 4,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
          }}
        >
          {description}
        </Typography>

        {/* Owner */}
        {ownerName && (
          <Box
            sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 2.5 }}
          >
            <Avatar
              src={ownerAvatar}
              alt={ownerName}
              sx={{ width: 24, height: 24, fontSize: '0.75rem' }}
            >
              {ownerName.charAt(0)}
            </Avatar>
            <Typography
              variant="caption"
              sx={{ color: theme.greyscale.text.body }}
            >
              {ownerName}
            </Typography>
          </Box>
        )}

        {/* Status Badge */}
        {statusLabel && (
          <Box sx={{ mb: hasFooter ? 2 : 0 }}>
            <Chip
              icon={
                <FiberManualRecordIcon
                  sx={{
                    fontSize: '8px !important',
                    color: 'inherit !important',
                  }}
                />
              }
              label={statusLabel}
              size="small"
              variant="outlined"
              sx={{
                borderRadius: theme.customRadius.full,
                borderColor: STATUS_COLOR_MAP[statusColor],
                color: STATUS_COLOR_MAP[statusColor],
                height: 24,
                '& .MuiChip-icon': {
                  color: `${STATUS_COLOR_MAP[statusColor]} !important`,
                  ml: 0.75,
                },
                '& .MuiChip-label': {
                  fontSize: '0.75rem',
                  px: 1,
                },
              }}
            />
          </Box>
        )}

        {/* Spacer to push chips to bottom */}
        <Box sx={{ flexGrow: 1 }} />

        {/* Chip Sections with Divider */}
        {hasFooter && (
          <Box>
            <Box
              sx={{
                width: '100%',
                height: '1px',
                bgcolor: 'divider',
                mb: 2,
              }}
            />
            {chipSections.map((section, sectionIndex) => {
              if (section.chips.length === 0) return null;
              const sectionKey =
                section.chips.map(c => c.key).join('-') ||
                `section-${sectionIndex}`;
              return (
                <Box
                  key={sectionKey}
                  sx={{ mb: sectionIndex < chipSections.length - 1 ? 1.5 : 0 }}
                >
                  {section.label && (
                    <Typography
                      variant="overline"
                      sx={{
                        display: 'block',
                        fontSize: '0.75rem',
                        letterSpacing: '0.04em',
                        color: theme.greyscale.text.subtitle,
                        lineHeight: 1.5,
                        mb: 1.25,
                      }}
                    >
                      {section.label}
                    </Typography>
                  )}
                  <Box
                    sx={{
                      display: 'flex',
                      flexWrap: 'wrap',
                      gap: 0.75,
                      '& .MuiChip-root': {
                        height: theme.spacing(2.75),
                        fontSize: theme.typography.caption.fontSize,
                        '& .MuiChip-icon': {
                          color: 'text.secondary',
                          marginLeft: theme.spacing(0.5),
                        },
                      },
                    }}
                  >
                    {section.chips.map(chip => (
                      <Chip
                        key={chip.key}
                        {...(chip.icon && {
                          icon: chip.icon as React.ReactElement,
                        })}
                        label={chip.label}
                        size="small"
                        variant={chip.variant || 'filled'}
                        sx={{
                          bgcolor: theme.greyscale.surface.default,
                          color: theme.greyscale.text.body,
                          borderRadius: `${theme.customRadius.m / 2}px`,
                          ...(chip.maxWidth && {
                            maxWidth: chip.maxWidth,
                            '& .MuiChip-label': {
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                            },
                          }),
                        }}
                      />
                    ))}
                  </Box>
                </Box>
              );
            })}
          </Box>
        )}
      </CardContent>
    </Card>
  );
}
