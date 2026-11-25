'use client';

import Box from '@mui/material/Box';
import Grid from '@mui/material/Grid';
import Typography from '@mui/material/Typography';
import { SectionCard } from '@/components/common/SectionCard';
import { SectionEditButton } from '@/components/common/SectionCardActions';
import ViewField from '@/components/common/ViewField';
import {
  noop,
  PLACEHOLDER_TEXT,
  TextPlaceholder,
} from '@/components/loading/TextPlaceholder';
import { SECTION_GRID } from '@/styles/theme-constants';

const DEFAULT_LINES = ['line-1', 'line-2', 'line-3'];

export interface SectionPlaceholderProps {
  /** The card's heading when it is static; a placeholder otherwise. */
  title?: string;
  subtitle?: string;
  /** Draw the card's Edit button (as a placeholder). */
  editable?: boolean;
  /** Labels of the card's read-only fields; their values wait. Without
   *  fields the card holds a few lines of text placeholders. */
  fields?: readonly string[];
  /** Fields per row from `md` up. */
  columns?: 1 | 2 | 3;
}

/**
 * A detail page's section card in a loading view: the real `SectionCard`
 * and `ViewField`s with the values left as placeholders. Must render inside
 * `SkeletonMode`.
 */
export default function SectionPlaceholder({
  title,
  subtitle,
  editable = false,
  fields,
  columns = 2,
}: SectionPlaceholderProps) {
  return (
    <SectionCard
      title={title}
      subtitle={subtitle}
      actions={editable ? <SectionEditButton onClick={noop} /> : undefined}
    >
      {/* Only values wait here; a screen reader would meet labels without
          them, so the card announces just its heading until they arrive. */}
      <Box inert sx={{ display: 'contents' }}>
        {!title && (
          <Typography variant="h6" sx={{ mb: 3 }}>
            <TextPlaceholder>{PLACEHOLDER_TEXT.crumb}</TextPlaceholder>
          </Typography>
        )}
        {fields ? (
          <Grid
            container
            columnSpacing={SECTION_GRID.columnSpacing}
            rowSpacing={SECTION_GRID.rowSpacing}
          >
            {fields.map(label => (
              <Grid key={label} size={{ xs: 12, md: 12 / columns }}>
                <ViewField label={label} value={PLACEHOLDER_TEXT.value} />
              </Grid>
            ))}
          </Grid>
        ) : (
          DEFAULT_LINES.map(key => (
            <Typography key={key} variant="body1">
              <TextPlaceholder>{PLACEHOLDER_TEXT.long}</TextPlaceholder>
            </Typography>
          ))
        )}
      </Box>
    </SectionCard>
  );
}
