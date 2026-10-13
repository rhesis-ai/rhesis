'use client';

import * as React from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import type { Theme } from '@mui/material/styles';
import { BORDER_RADIUS } from '@/styles/theme-constants';
import { resourceDisplayName } from '../../shared/resource-catalog';
import { splitAction } from '../labels';
import {
  FieldChangeKind,
  type AuditEventDetail,
  type ContentChange,
  type FieldChange,
} from '../types';

const EMPTY_VALUE = '(none)';
const SECRET_TEXT = 'Changed. Secret values are never recorded.';
const HIDDEN_CONTENT_TEXT = 'Changed (content hidden)';
/** Ids beyond this are counted, not listed. */
const MAX_LISTED_IDS = 20;

export const monoSx = {
  fontFamily: 'monospace',
  wordBreak: 'break-all',
} as const;

export function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return EMPTY_VALUE;
  if (Array.isArray(value)) {
    return value.length === 0 ? EMPTY_VALUE : value.map(formatValue).join(', ');
  }
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

function isFieldChangeList(changes: unknown): changes is FieldChange[] {
  return (
    Array.isArray(changes) &&
    changes.every(
      c => typeof c === 'object' && c !== null && 'field' in c && 'kind' in c
    )
  );
}

const tableSx = {
  display: 'grid',
  gridTemplateColumns: (t: Theme) => `minmax(${t.spacing(14)}, 1fr) 2fr 2fr`,
  border: (t: Theme) => `1px solid ${t.palette.greyscale.border}`,
  borderRadius: BORDER_RADIUS.sm,
  overflow: 'hidden',
  '& > *': {
    px: 1.5,
    py: 1,
    borderTop: (t: Theme) => `1px solid ${t.palette.greyscale.border}`,
    minWidth: 0,
  },
  '& > .header': {
    borderTop: 'none',
    bgcolor: 'action.hover',
  },
};

function Cell({
  children,
  header = false,
  muted = false,
  span = 1,
}: {
  children: React.ReactNode;
  header?: boolean;
  muted?: boolean;
  span?: number;
}) {
  return (
    <Box
      className={header ? 'header' : undefined}
      sx={{ gridColumn: span > 1 ? `span ${span}` : undefined }}
    >
      <Typography
        variant={header ? 'caption' : 'body2'}
        color={header || muted ? 'text.secondary' : 'text.primary'}
        sx={header ? undefined : monoSx}
      >
        {children}
      </Typography>
    </Box>
  );
}

function FieldRow({
  change,
  content,
}: {
  change: FieldChange;
  content: ContentChange | undefined;
}) {
  if (change.kind === FieldChangeKind.SECRET) {
    return (
      <>
        <Cell>{change.field}</Cell>
        <Cell span={2} muted>
          {SECRET_TEXT}
        </Cell>
      </>
    );
  }
  if (change.kind === FieldChangeKind.CONTENT && !content) {
    return (
      <>
        <Cell>{change.field}</Cell>
        <Cell span={2} muted>
          {HIDDEN_CONTENT_TEXT}
        </Cell>
      </>
    );
  }
  const source = change.kind === FieldChangeKind.CONTENT ? content : change;
  return (
    <>
      <Cell>{change.field}</Cell>
      <Cell>{formatValue(source?.before)}</Cell>
      <Cell>{formatValue(source?.after)}</Cell>
    </>
  );
}

/** A job's bulk create (`{count, ids}`) or a purge (`{count, oldest, before}`). */
function SummaryChanges({
  summary,
  action,
}: {
  summary: Record<string, unknown>;
  action: string;
}) {
  const count = typeof summary.count === 'number' ? summary.count : null;
  const ids = Array.isArray(summary.ids) ? summary.ids.map(String) : null;
  const rest = Object.entries(summary).filter(
    ([key]) => key !== 'count' && key !== 'ids'
  );
  const { resource, verb } = splitAction(action);

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      {count !== null && (
        <Typography variant="body2">
          {resourceDisplayName(resource)} {verb.replace(/_/g, ' ')}:{' '}
          <strong>{count.toLocaleString()}</strong>
        </Typography>
      )}
      {rest.length > 0 && (
        <Box sx={tableSx}>
          {rest.map(([key, value]) => (
            <React.Fragment key={key}>
              <Cell>{key}</Cell>
              <Cell span={2}>{formatValue(value)}</Cell>
            </React.Fragment>
          ))}
        </Box>
      )}
      {ids && ids.length > 0 && (
        <Box>
          <Typography variant="caption" color="text.secondary">
            Ids
          </Typography>
          <Typography variant="body2" sx={monoSx}>
            {ids.slice(0, MAX_LISTED_IDS).join(', ')}
            {ids.length > MAX_LISTED_IDS &&
              ` and ${(ids.length - MAX_LISTED_IDS).toLocaleString()} more`}
          </Typography>
        </Box>
      )}
      {ids && ids.length === 0 && count !== null && (
        <Typography variant="body2" color="text.secondary">
          Too many to list; the count is exact.
        </Typography>
      )}
    </Box>
  );
}

export default function AuditChanges({ event }: { event: AuditEventDetail }) {
  const { changes } = event;

  if (isFieldChangeList(changes)) {
    if (changes.length === 0) {
      return (
        <Typography variant="body2" color="text.secondary">
          No field changes recorded for this event.
        </Typography>
      );
    }
    const content = new Map(
      (event.content_changes ?? []).map(c => [c.field, c])
    );
    return (
      <Box sx={tableSx}>
        <Cell header>Field</Cell>
        <Cell header>Before</Cell>
        <Cell header>After</Cell>
        {changes.map(change => (
          <FieldRow
            key={change.field}
            change={change}
            content={content.get(change.field)}
          />
        ))}
      </Box>
    );
  }

  if (changes && typeof changes === 'object' && !Array.isArray(changes)) {
    return <SummaryChanges summary={changes} action={event.action} />;
  }

  return (
    <Typography variant="body2" color="text.secondary">
      No field changes recorded for this event.
    </Typography>
  );
}
