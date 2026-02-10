import React from 'react';
import { useTheme } from '@mui/material/styles';
import { Card, CardContent, Typography, Box, Chip } from '@mui/material';

export interface ChipData {
  key: string;
  icon?: React.ReactNode;
  label: string;
  variant?: 'filled' | 'outlined';
  maxWidth?: string;
  tooltip?: string;
}

export interface ChipSection {
  chips: ChipData[];
}

interface EntityCardProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  topRightActions?: React.ReactNode;
  captionText?: string;
  chipSections: ChipSection[];
}

export default function EntityCard({
  icon,
  title,
  description,
  topRightActions,
  captionText,
  chipSections,
}: EntityCardProps) {
  const theme = useTheme();

  const chipStyles = {
    '& .MuiChip-icon': {
      color: 'text.secondary',
      marginLeft: theme.spacing(0.5),
    },
  };

  return (
    <Card
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        position: 'relative',
      }}
    >
      {topRightActions && (
        <Box
          sx={{
            position: 'absolute',
            top: 8,
            right: 8,
            display: 'flex',
            gap: 1,
            zIndex: 1,
          }}
        >
          {topRightActions}
        </Box>
      )}
      <CardContent
        sx={{
          flexGrow: 1,
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          pb: 2,
          pt: 3,
        }}
      >
        <Box>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 1.5 }}>
            <Box
              sx={{
                mr: 1.5,
                color: 'primary.main',
                display: 'flex',
                alignItems: 'center',
              }}
            >
              {icon}
            </Box>
            <Typography
              variant="subtitle1"
              component="div"
              sx={{
                fontWeight: 500,
                lineHeight: 1.2,
                maxWidth: '30ch',
                wordWrap: 'break-word',
                overflowWrap: 'break-word',
                flex: 1,
              }}
            >
              {title}
            </Typography>
          </Box>

          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ mb: 'auto', minHeight: '2.5em' }}
          >
            {description}
          </Typography>
        </Box>

        <Box sx={{ mt: 2 }}>
          {captionText && (
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{
                display: 'block',
                mb: 1,
                minHeight: '1.5em',
              }}
            >
              {captionText}
            </Typography>
          )}

          {chipSections.map((section, sectionIndex) => (
            <React.Fragment key={section.chips[0]?.key ?? `section-${sectionIndex}`}>
              {sectionIndex > 0 && (
                <Box
                  sx={{
                    width: '100%',
                    height: '1px',
                    bgcolor: 'divider',
                    my: 1,
                  }}
                />
              )}
              <Box
                sx={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: 0.5,
                  mb: sectionIndex < chipSections.length - 1 ? 1 : 0,
                  '& .MuiChip-root': {
                    height: theme.spacing(3),
                    fontSize: theme.typography.caption.fontSize,
                    ...chipStyles,
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
                    variant={chip.variant || 'outlined'}
                    sx={{
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
            </React.Fragment>
          ))}
        </Box>
      </CardContent>
    </Card>
  );
}
