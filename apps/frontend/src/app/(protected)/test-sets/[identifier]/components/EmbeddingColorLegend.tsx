'use client';

import { Box, Stack, Typography } from '@mui/material';
import type { EmbeddingColorLegendEntry } from '@/utils/embedding/embeddingColorBy';

interface EmbeddingColorLegendProps {
  entries: EmbeddingColorLegendEntry[];
}

export default function EmbeddingColorLegend({
  entries,
}: EmbeddingColorLegendProps) {
  if (entries.length === 0) return null;

  return (
    <Box
      sx={{
        position: 'absolute',
        left: 8,
        bottom: 8,
        zIndex: 2,
        maxWidth: '55%',
        maxHeight: 140,
        overflow: 'auto',
        p: 1,
        borderRadius: 1,
        bgcolor: 'background.paper',
        border: 1,
        borderColor: 'divider',
        boxShadow: 1,
      }}
    >
      <Stack spacing={0.5}>
        {entries.map(entry => (
          <Stack
            key={entry.label}
            direction="row"
            alignItems="center"
            spacing={0.75}
          >
            <Box
              sx={{
                width: 10,
                height: 10,
                borderRadius: '50%',
                bgcolor: entry.color,
                flexShrink: 0,
                border: 1,
                borderColor: 'divider',
              }}
            />
            <Typography
              variant="caption"
              sx={{
                lineHeight: 1.2,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
              title={`${entry.label} (${entry.count})`}
            >
              {entry.label}
              <Typography
                component="span"
                variant="caption"
                color="text.secondary"
                sx={{ ml: 0.5 }}
              >
                ({entry.count})
              </Typography>
            </Typography>
          </Stack>
        ))}
      </Stack>
    </Box>
  );
}
