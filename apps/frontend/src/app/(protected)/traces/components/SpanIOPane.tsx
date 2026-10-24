'use client';

import { useState } from 'react';
import {
  Box,
  Button,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import type { Theme } from '@mui/material/styles';
import { BORDER_RADIUS } from '@/styles/theme';
import { JsonPreview } from '@/app/(protected)/endpoints/components/JsonPreview';
import CopyButton from './CopyButton';
import type { LlmMessage } from './span-io';

type Format = 'pretty' | 'json';

interface SpanIOPaneProps {
  title: string;
  /** Plain values; a label shows only when there is more than one kind (args vs kwargs). */
  entries?: { label?: string; value: unknown }[];
  /** LLM prompt messages, shown one row per message. */
  messages?: LlmMessage[];
}

const monoSx = (theme: Theme) => ({
  fontFamily: theme.typography.fontFamilyCode,
});

const isPlainObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

function asText(value: unknown): string {
  return typeof value === 'string' ? value : JSON.stringify(value, null, 2);
}

function JsonBlock({ value }: { value: unknown }) {
  return (
    <Box
      component="pre"
      sx={theme => ({
        ...monoSx(theme),
        m: 0,
        typography: 'caption',
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
      })}
    >
      <JsonPreview value={value} />
    </Box>
  );
}

function Text({ value }: { value: string }) {
  return (
    <Typography
      variant="body2"
      sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', m: 0 }}
    >
      {value}
    </Typography>
  );
}

/** A value read like a form: top-level keys as rows, strings as prose, the rest as JSON. */
function PrettyValue({ value }: { value: unknown }) {
  if (typeof value === 'string') return <Text value={value} />;
  if (!isPlainObject(value)) return <JsonBlock value={value} />;

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75 }}>
      {Object.entries(value).map(([key, inner]) => (
        <Box key={key} sx={{ display: 'flex', gap: 1.5, minWidth: 0 }}>
          <Typography
            variant="caption"
            sx={theme => ({
              ...monoSx(theme),
              color: 'text.secondary',
              flexShrink: 0,
              minWidth: theme.spacing(11),
              pt: 0.25,
            })}
          >
            {key}
          </Typography>
          <Box sx={{ flex: 1, minWidth: 0 }}>
            {typeof inner === 'string' ? (
              <Text value={inner} />
            ) : (
              <JsonBlock value={inner} />
            )}
          </Box>
        </Box>
      ))}
    </Box>
  );
}

/** Long system prompts are clamped to three lines until opened. */
function MessageRow({ message }: { message: LlmMessage }) {
  const isSystem = message.role === 'system';
  const [open, setOpen] = useState(!isSystem);
  const text = asText(message.content ?? '');

  return (
    <Box sx={{ display: 'flex', gap: 1.5, py: 1, minWidth: 0 }}>
      <Typography
        variant="caption"
        sx={theme => ({
          width: theme.spacing(9),
          flexShrink: 0,
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: theme.typography.overline.letterSpacing,
          color: 'text.secondary',
          pt: 0.25,
        })}
      >
        {message.role}
      </Typography>
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Typography
          variant="body2"
          sx={{
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            ...(open
              ? {}
              : {
                  display: '-webkit-box',
                  WebkitLineClamp: 3,
                  WebkitBoxOrient: 'vertical',
                  overflow: 'hidden',
                }),
          }}
        >
          {text}
        </Typography>
        {isSystem && (
          <Button
            size="small"
            variant="text"
            onClick={() => setOpen(o => !o)}
            sx={{ p: 0, minWidth: 0, textTransform: 'none' }}
          >
            {open ? 'Show less' : 'Show all'}
          </Button>
        )}
      </Box>
    </Box>
  );
}

/**
 * One input or output, bordered and scrollable, with a Pretty/JSON switch for
 * structured values and a copy button.
 */
export default function SpanIOPane({
  title,
  entries = [],
  messages,
}: SpanIOPaneProps) {
  const [format, setFormat] = useState<Format>('pretty');
  const raw = messages ?? (entries.length === 1 ? entries[0].value : entries);
  const structured =
    !!messages || entries.some(e => typeof e.value !== 'string');

  return (
    <Box>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          minHeight: theme => theme.spacing(3.5),
        }}
      >
        <Typography
          variant="caption"
          component="h3"
          sx={{ fontWeight: 600, color: 'text.primary' }}
        >
          {title}
          {messages && (
            <Box
              component="span"
              sx={{ fontWeight: 400, color: 'text.secondary' }}
            >
              {` · ${messages.length} ${messages.length === 1 ? 'message' : 'messages'}`}
            </Box>
          )}
        </Typography>
        <Box sx={{ flex: 1 }} />
        {structured && (
          <ToggleButtonGroup
            value={format}
            exclusive
            size="small"
            aria-label={`${title} format`}
            onChange={(_, value: Format | null) => value && setFormat(value)}
          >
            <ToggleButton
              value="pretty"
              sx={{
                py: 0,
                px: 1,
                typography: 'caption',
                textTransform: 'none',
              }}
            >
              {messages ? 'Messages' : 'Pretty'}
            </ToggleButton>
            <ToggleButton
              value="json"
              sx={{
                py: 0,
                px: 1,
                typography: 'caption',
                textTransform: 'none',
              }}
            >
              JSON
            </ToggleButton>
          </ToggleButtonGroup>
        )}
        <CopyButton text={asText(raw)} label={`Copy ${title.toLowerCase()}`} />
      </Box>

      <Box
        sx={{
          mt: 0.5,
          border: 1,
          borderColor: 'divider',
          borderRadius: BORDER_RADIUS.sm,
          bgcolor: 'greyscale.fieldSurface',
          px: 1.5,
          py: messages && format === 'pretty' ? 0 : 1,
          maxHeight: theme => theme.spacing(45),
          overflow: 'auto',
        }}
      >
        {format === 'json' ? (
          <JsonBlock value={raw} />
        ) : messages ? (
          <Box
            sx={{
              '& > * + *': { borderTop: 1, borderColor: 'divider' },
            }}
          >
            {messages.map((message, i) => (
              // eslint-disable-next-line react/no-array-index-key -- prompt messages have no id and never reorder
              <MessageRow key={i} message={message} />
            ))}
          </Box>
        ) : (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            {entries.map((entry, i) => (
              // eslint-disable-next-line react/no-array-index-key -- at most args then kwargs, fixed order
              <Box key={i}>
                {entry.label && (
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{ display: 'block', mb: 0.25 }}
                  >
                    {entry.label}
                  </Typography>
                )}
                <PrettyValue value={entry.value} />
              </Box>
            ))}
          </Box>
        )}
      </Box>
    </Box>
  );
}
