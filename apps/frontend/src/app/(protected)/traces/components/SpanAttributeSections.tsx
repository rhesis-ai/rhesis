'use client';

import { useState } from 'react';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  Typography,
} from '@mui/material';
import type { Theme } from '@mui/material/styles';
import { ChevronRightIcon } from '@/components/icons';
import { JsonPreview } from '@/app/(protected)/endpoints/components/JsonPreview';
import type { SpanNode } from '@/utils/api-client/interfaces/telemetry';
import CopyButton from './CopyButton';
import type { SpanAttributeGroups } from './span-io';

const monoCaptionSx = (theme: Theme) => ({
  ...theme.typography.caption,
  fontFamily: theme.typography.fontFamilyCode,
});

function valueText(value: unknown): string {
  return typeof value === 'object' && value !== null
    ? JSON.stringify(value)
    : String(value);
}

/** One line per attribute; a long value opens in place on click. */
function AttributeRow({ name, value }: { name: string; value: unknown }) {
  const [open, setOpen] = useState(false);
  const text = valueText(value);

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: open ? 'flex-start' : 'center',
        gap: 1.5,
        py: 0.5,
        borderBottom: 1,
        borderColor: 'divider',
        '&:last-of-type': { borderBottom: 0 },
        '& .copy': { visibility: 'hidden' },
        '&:hover .copy, &:focus-within .copy': { visibility: 'visible' },
      }}
    >
      <Box
        component="span"
        title={name}
        sx={theme => ({
          ...monoCaptionSx(theme),
          color: 'text.secondary',
          flex: '0 1 auto',
          maxWidth: '40%',
          minWidth: theme.spacing(12),
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        })}
      >
        {name}
      </Box>
      <Box
        component="button"
        type="button"
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
        sx={theme => ({
          ...monoCaptionSx(theme),
          flex: 1,
          minWidth: 0,
          p: 0,
          border: 0,
          bgcolor: 'transparent',
          color: 'text.primary',
          textAlign: 'left',
          cursor: 'pointer',
          ...(open
            ? { whiteSpace: 'pre-wrap', wordBreak: 'break-word' }
            : {
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }),
        })}
      >
        {text}
      </Box>
      <Box className="copy" sx={{ flexShrink: 0 }}>
        <CopyButton text={text} label={`Copy ${name}`} />
      </Box>
    </Box>
  );
}

export function AttributesTable({
  attributes,
}: {
  attributes: Record<string, unknown>;
}) {
  return (
    <Box>
      {Object.entries(attributes).map(([key, value]) => (
        <AttributeRow key={key} name={key} value={value} />
      ))}
    </Box>
  );
}

function Section({
  title,
  count,
  summary,
  children,
}: {
  title: string;
  count?: number;
  summary?: string;
  children: React.ReactNode;
}) {
  return (
    <Accordion
      disableGutters
      square
      elevation={0}
      slotProps={{ transition: { unmountOnExit: true } }}
      sx={{
        bgcolor: 'transparent',
        borderBottom: 1,
        borderColor: 'divider',
        '&::before': { display: 'none' },
      }}
    >
      <AccordionSummary
        sx={{
          minHeight: theme => theme.spacing(4),
          px: 2,
          flexDirection: 'row-reverse',
          gap: 0.75,
          '& .MuiAccordionSummary-content': {
            my: 0,
            gap: 1,
            alignItems: 'center',
          },
          '& .MuiAccordionSummary-expandIconWrapper.Mui-expanded': {
            transform: 'rotate(90deg)',
          },
          '&:hover': { bgcolor: 'action.hover' },
        }}
        expandIcon={
          <ChevronRightIcon sx={{ fontSize: theme => theme.spacing(2) }} />
        }
      >
        <Typography variant="caption" sx={{ fontWeight: 600 }}>
          {title}
        </Typography>
        {count !== undefined && (
          <Typography variant="caption" color="text.secondary">
            {count}
          </Typography>
        )}
        {summary && (
          <Typography variant="caption" color="text.secondary" noWrap>
            {summary}
          </Typography>
        )}
      </AccordionSummary>
      <AccordionDetails sx={{ pt: 0, pb: 1, pl: 5, pr: 2 }}>
        {children}
      </AccordionDetails>
    </Accordion>
  );
}

interface SpanAttributeSectionsProps {
  span: SpanNode;
  groups: SpanAttributeGroups;
  /** Rendered as the first section, e.g. per-turn file attachments. */
  attachments?: React.ReactNode;
  attachmentCount?: number;
}

/** Everything that is not input or output, folded away by default. */
export default function SpanAttributeSections({
  span,
  groups,
  attachments,
  attachmentCount,
}: SpanAttributeSectionsProps) {
  const lists: { title: string; attributes: Record<string, unknown> }[] = [
    { title: 'LLM attributes', attributes: groups.llm },
    { title: 'Function attributes', attributes: groups.function },
    { title: 'Test attributes', attributes: groups.test },
    { title: 'Other attributes', attributes: groups.other },
  ];

  return (
    <Box sx={{ borderTop: 1, borderColor: 'divider' }}>
      {attachments && (
        <Section title="Attachments" count={attachmentCount}>
          {attachments}
        </Section>
      )}
      {lists
        .filter(list => Object.keys(list.attributes).length > 0)
        .map(list => (
          <Section
            key={list.title}
            title={list.title}
            count={Object.keys(list.attributes).length}
          >
            <AttributesTable attributes={list.attributes} />
          </Section>
        ))}
      {groups.versionInfo && (
        <Section title="Version information">
          <Box
            component="pre"
            sx={theme => ({
              ...monoCaptionSx(theme),
              m: 0,
              whiteSpace: 'pre-wrap',
            })}
          >
            <JsonPreview value={groups.versionInfo} />
          </Box>
        </Section>
      )}
      {span.events && span.events.length > 0 && (
        <Section title="Events" count={span.events.length}>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            {span.events.map((event, idx) => (
              <Box
                key={`${event.name}-${event.timestamp || idx}`}
                component="pre"
                sx={theme => ({
                  ...monoCaptionSx(theme),
                  m: 0,
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                })}
              >
                <JsonPreview value={event} />
              </Box>
            ))}
          </Box>
        </Section>
      )}
    </Box>
  );
}
