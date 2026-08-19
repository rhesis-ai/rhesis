'use client';

import { Box, Typography } from '@mui/material';
import { quotaCopy, type QuotaZone } from '@/utils/quota';
import type { QuotaResource } from '@/constants/quota';

export interface QuotaNoticeProps {
  resource: QuotaResource;
  kind: 'flow' | 'stock' | undefined;
  used: number;
  limit: number;
  zone: Exclude<QuotaZone, 'healthy'>;
  periodEnd?: string;
  canUpgrade: boolean;
}

/**
 * The inline-gate notice: what `BaseDrawer`'s `error` slot renders for a
 * quota gate that isn't a failure. Shared by every drawer's preflight gate
 * and its reactive 402 catch (`parseQuotaError`) -- one place turns a
 * `quotaCopy()` result into markup, so the sentence and recourse always
 * read together the same way.
 *
 * `approaching`/`pastIncluded` render in warning tones because nothing is
 * actually blocked yet; only `blocked` renders as an error.
 */
export function QuotaNotice(props: QuotaNoticeProps) {
  const { zone } = props;
  const { sentence, recourse } = quotaCopy(props);
  const color =
    zone === 'blocked'
      ? 'error.main'
      : zone === 'pastIncluded'
        ? 'warning.dark'
        : 'warning.main';

  return (
    <Box>
      <Typography variant="body2" sx={{ color, fontWeight: 600 }}>
        {sentence}
      </Typography>
      {recourse && (
        <Typography variant="caption" color="text.secondary" component="div">
          {recourse}
        </Typography>
      )}
    </Box>
  );
}
