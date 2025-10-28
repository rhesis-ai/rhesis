'use client';

import React, { useState } from 'react';
import {
  Box,
  Typography,
  IconButton,
  Popover,
  Paper,
  Chip,
  Stack,
  Divider,
} from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import DescriptionIcon from '@mui/icons-material/Description';

interface ContextPreviewProps {
  context?: Array<{ name: string; description?: string; content?: string }>;
}

/**
 * ContextPreview Component
 * Shows a small info icon that on click reveals which sources/context were used for the test
 */
export default function ContextPreview({ context }: ContextPreviewProps) {
  const [anchorEl, setAnchorEl] = useState<HTMLButtonElement | null>(null);

  const handleClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const open = Boolean(anchorEl);

  // Don't show anything if no context
  if (!context || context.length === 0) {
    return null;
  }

  return (
    <>
      <IconButton
        size="small"
        onClick={handleClick}
        sx={{
          color: 'primary.main',
          '&:hover': { bgcolor: 'action.hover' },
        }}
        aria-label="show context"
      >
        <InfoOutlinedIcon fontSize="small" />
      </IconButton>

      <Popover
        open={open}
        anchorEl={anchorEl}
        onClose={handleClose}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'left',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'left',
        }}
      >
        <Paper sx={{ p: 2, maxWidth: 500, maxHeight: 600, overflow: 'auto' }}>
          <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: 600 }}>
            Context Sources
          </Typography>
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ display: 'block', mb: 1.5 }}
          >
            Sources used to generate this test
          </Typography>

          <Stack spacing={2}>
            {context.map((source, index) => (
              <Box key={index}>
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 1,
                    p: 1,
                    borderRadius: 1,
                    bgcolor: 'action.hover',
                    mb: 1,
                  }}
                >
                  <DescriptionIcon fontSize="small" color="action" />
                  <Box sx={{ flex: 1 }}>
                    <Typography variant="body2" sx={{ fontWeight: 500 }}>
                      {source.name}
                    </Typography>
                    {source.description && (
                      <Typography variant="caption" color="text.secondary">
                        {source.description}
                      </Typography>
                    )}
                  </Box>
                </Box>
                {source.content && (
                  <>
                    <Divider sx={{ my: 1 }} />
                    <Box
                      sx={{
                        maxHeight: 200,
                        overflow: 'auto',
                        bgcolor: 'background.default',
                        p: 1.5,
                        borderRadius: 1,
                      }}
                    >
                      <Typography
                        variant="body2"
                        sx={{
                          fontSize: '0.75rem',
                          lineHeight: 1.5,
                          whiteSpace: 'pre-wrap',
                          color: 'text.secondary',
                        }}
                      >
                        {source.content}
                      </Typography>
                    </Box>
                  </>
                )}
              </Box>
            ))}
          </Stack>
        </Paper>
      </Popover>
    </>
  );
}

