'use client';

import React, { useState } from 'react';
import {
  Box,
  Typography,
  Popover,
  Paper,
  Stack,
  Divider,
  Tooltip,
} from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import DescriptionIcon from '@mui/icons-material/Description';

interface ContextPreviewProps {
  context?: Array<{ name: string; content?: string }>;
}

/**
 * ContextPreview Component
 * Shows a small info icon that on click reveals which sources/context were used for the test
 */
export default function ContextPreview({ context }: ContextPreviewProps) {
  const [anchorEl, setAnchorEl] = useState<SVGSVGElement | null>(null);

  const handleClick = (event: React.MouseEvent<SVGSVGElement>) => {
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
      <Tooltip
        title="Click to view the portion of source used to generate this test"
        arrow
        placement="top"
      >
        <InfoOutlinedIcon
          onClick={handleClick}
          sx={{
            fontSize: 14,
            opacity: 0.7,
            cursor: 'help',
            '&:hover': { opacity: 1 },
          }}
        />
      </Tooltip>

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
          <Stack spacing={2}>
            {context.map((source, index) => (
              <Box key={`${source.name}-${index}`}>
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 1,
                    p: 1,
                    borderRadius: theme => theme.shape.borderRadius,
                    bgcolor: 'action.hover',
                    mb: 1,
                  }}
                >
                  <DescriptionIcon fontSize="small" color="action" />
                  <Box sx={{ flex: 1 }}>
                    <Typography variant="body2" sx={{ fontWeight: 500 }}>
                      {source.name}
                    </Typography>
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
                        borderRadius: theme => theme.shape.borderRadius,
                      }}
                    >
                      <Typography
                        variant="caption"
                        sx={{
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
