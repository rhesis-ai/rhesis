import React from 'react';
import { Box, Paper, Typography } from '@mui/material';
import { SectionEditButton } from '@/components/common/SectionCardActions';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme-constants';

interface GeneralInfoCardProps {
  /** Card heading — defaults to "General Information". */
  title?: string;
  /** When provided, an Edit button is shown next to the title. */
  onEdit?: () => void;
  children: React.ReactNode;
}

/**
 * Figma-aligned white Paper card used in entity detail "Basic Information" tabs.
 * Renders a section heading (teal H6) with an optional Edit button, then any children.
 */
export function GeneralInfoCard({
  title = 'General Information',
  onEdit,
  children,
}: GeneralInfoCardProps) {
  return (
    <Paper
      elevation={0}
      sx={{
        border: theme => `1px solid ${theme.palette.greyscale.border}`,
        borderRadius: BORDER_RADIUS.lg,
        boxShadow: ELEVATION.xs,
        px: '30px',
        py: '40px',
      }}
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          mb: 3,
        }}
      >
        <Typography
          variant="h6"
          sx={{ fontWeight: 600, fontSize: 20, color: 'primary.main' }}
        >
          {title}
        </Typography>

        {onEdit && <SectionEditButton onClick={onEdit} />}
      </Box>

      {children}
    </Paper>
  );
}

export default GeneralInfoCard;
