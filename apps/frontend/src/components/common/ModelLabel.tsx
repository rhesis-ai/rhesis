'use client';

import React from 'react';
import { Tooltip, Typography } from '@mui/material';
import type { SxProps, Theme } from '@mui/material/styles';

interface ModelLabelProps {
  /** Distinct models, empty when nothing was priced. */
  models?: string[] | null;
  /** Distinct providers behind them, used to qualify the first model. */
  providers?: string[] | null;
  /** Element to render as. Pass `span` when this sits inside another
   *  Typography, since a <p> nested in a <p> is invalid and React warns.
   *  Defaults to `p`, which is what body2 maps to anyway. */
  component?: 'p' | 'span';
  /** Clip to one line with an ellipsis. True for grid cells, which have a fixed
   *  column width. False where the name matters more than the line count -- a
   *  half-shown `gemini/ge...` tells the reader nothing. */
  truncate?: boolean;
  /** Merged over the label's own styles, so a caller can have the name inherit
   *  the weight and colour of the line it sits on. */
  sx?: SxProps<Theme>;
}

/**
 * The model behind a row's cost, as `provider/model`.
 *
 * Shared by the test runs grid and the traces grid so the same trace is described the
 * same way in both. Where several models contributed it shows the first with a `+N`,
 * matching the field those grids sort by, and the full list on hover.
 *
 * An empty list renders a dash rather than nothing: the row still has to occupy its
 * column, and a dash says "we do not know" where a blank would read as an oversight.
 */
export default function ModelLabel({
  models,
  providers,
  component = 'p',
  truncate = true,
  sx,
}: ModelLabelProps) {
  const names = models ?? [];
  if (names.length === 0) {
    return (
      <Typography
        variant="body2"
        component={component}
        sx={{ color: 'text.disabled' }}
      >
        —
      </Typography>
    );
  }

  const provider = providers?.[0];
  const first = provider ? `${provider}/${names[0]}` : names[0];
  const label = names.length > 1 ? `${first} +${names.length - 1}` : first;

  const text = (
    <Typography
      variant="body2"
      component={component}
      sx={[
        truncate
          ? {
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }
          : { wordBreak: 'break-word' },
        ...(Array.isArray(sx) ? sx : sx ? [sx] : []),
      ]}
    >
      {label}
    </Typography>
  );

  // One model is already named in full, so there is nothing for a tooltip to
  // reveal. MUI refuses to open an empty one, but it still wraps the child and
  // listens for hover and focus to decide that.
  if (names.length === 1) return text;

  return <Tooltip title={names.join(', ')}>{text}</Tooltip>;
}
