'use client';

import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import {
  PLACEHOLDER_TEXT,
  TextPlaceholder,
} from '@/components/loading/TextPlaceholder';
import { rem } from '@/styles/theme-constants';

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
              fontSize: rem(12),
              lineHeight: rem(18),
              color: theme => theme.palette.greyscale.body,
            }}
          >
            {label}
          </Typography>
          <Typography
            variant="caption"
            sx={{
              fontSize: rem(12),
              lineHeight: rem(18),
              color: theme => theme.palette.greyscale.subtitle,
            }}
          >
            {/* The value itself outside skeleton mode. */}
            <TextPlaceholder>{value}</TextPlaceholder>
          </Typography>
        </Box>
      ))}
    </Box>
  );
}

/** The usual "created by / created on" strip while the record loads; the
 *  values are placeholders in skeleton mode. */
export function CreatedMetadataPlaceholder() {
  return (
    <DetailMetadataStrip
      items={[
        { label: 'created by:', value: PLACEHOLDER_TEXT.person },
        { label: 'created on:', value: PLACEHOLDER_TEXT.date },
      ]}
    />
  );
}
