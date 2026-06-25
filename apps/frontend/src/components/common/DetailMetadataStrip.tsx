'use client';

import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';

interface MetadataItem {
  label: string;
  value: string;
}

interface DetailMetadataStripProps {
  items: MetadataItem[];
}

/**
 * Theme-aware metadata strip for detail pages (e.g. "created by / created on").
 * Must live in a Client Component so MUI sx theme callbacks can be used.
 * Server Component pages pass plain string data; styling happens here on the client.
 */
export default function DetailMetadataStrip({
  items,
}: DetailMetadataStripProps) {
  return (
    <Box sx={{ display: 'flex', gap: '30px' }}>
      {items.map(({ label, value }) => (
        <Box key={label} sx={{ display: 'flex', gap: 0.5 }}>
          <Typography
            variant="caption"
            sx={{
              fontSize: 12,
              lineHeight: '18px',
              color: theme => theme.palette.greyscale.body,
            }}
          >
            {label}
          </Typography>
          <Typography
            variant="caption"
            sx={{
              fontSize: 12,
              lineHeight: '18px',
              color: theme => theme.palette.greyscale.subtitle,
            }}
          >
            {value}
          </Typography>
        </Box>
      ))}
    </Box>
  );
}
