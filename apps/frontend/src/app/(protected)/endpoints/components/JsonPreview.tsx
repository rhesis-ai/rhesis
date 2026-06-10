'use client';

import { Fragment } from 'react';
import { Box } from '@mui/material';
import { alpha, type Theme } from '@mui/material/styles';

// ── Output variables ──────────────────────────────────────────────────────────

export const OUTPUT_VARIABLES = [
  {
    name: 'output',
    label: '{{ output }}',
    description:
      'Required. The text your model returned — this is what Rhesis scores.',
  },
  {
    name: 'conversation_id',
    label: '{{ conversation_id }}',
    description: 'Conversation ID for multi-turn tracking.',
  },
  {
    name: 'context',
    label: '{{ context }}',
    description:
      'Retrieved documents or sources — used by context-dependent metrics.',
  },
  {
    name: 'metadata',
    label: '{{ metadata }}',
    description:
      'Structured data (model version, token counts…). Stored with the result.',
  },
  {
    name: 'tool_calls',
    label: '{{ tool_calls }}',
    description: 'Tool or function calls made during response generation.',
  },
];

// ── Token colours ─────────────────────────────────────────────────────────────

const T = {
  str: (t: Theme) => (t.palette.mode === 'dark' ? '#ce9178' : '#a31515'), // Intentional: syntax-highlighting token, no theme equivalent
  num: (t: Theme) => (t.palette.mode === 'dark' ? '#b5cea8' : '#098658'), // Intentional: syntax-highlighting token, no theme equivalent
  kw: (t: Theme) => (t.palette.mode === 'dark' ? '#569cd6' : '#0070c1'), // Intentional: syntax-highlighting token, no theme equivalent
  bracket: 'text.secondary',
  comma: 'text.disabled',
  key: 'text.secondary',
};

const varChipSx = {
  bgcolor: (t: Theme) => alpha(t.palette.primary.main, 0.12),
  color: 'primary.main',
  px: '4px',
  py: '1px',
  borderRadius: '3px',
  fontWeight: 600,
};

// ── Read-only JSON tree (with optional interactive key clicks) ────────────────

export interface JsonPreviewProps {
  value: unknown;
  path?: string;
  depth?: number;
  comma?: boolean;
  /** path (no leading $.) → variable name — mapped values render as blue chips */
  pathToVar?: Record<string, string>;
  /** When provided, object keys become clickable */
  onKeyClick?: (path: string, el: HTMLElement) => void;
}

export function JsonPreview({
  value,
  path = '',
  depth = 0,
  comma = false,
  pathToVar = {},
  onKeyClick,
}: JsonPreviewProps) {
  const indent = (n: number) => ' '.repeat(n * 2);
  const tail = comma ? (
    <Box component="span" sx={{ color: T.comma }}>
      ,
    </Box>
  ) : null;

  const mappedVar = pathToVar[path];
  if (mappedVar !== undefined) {
    return (
      <>
        <Box component="span" sx={varChipSx}>{`{{ ${mappedVar} }}`}</Box>
        {tail}
      </>
    );
  }

  if (value === null)
    return (
      <>
        <Box component="span" sx={{ color: T.kw }}>
          null
        </Box>
        {tail}
      </>
    );
  if (typeof value === 'boolean')
    return (
      <>
        <Box component="span" sx={{ color: T.kw }}>
          {String(value)}
        </Box>
        {tail}
      </>
    );
  if (typeof value === 'number')
    return (
      <>
        <Box component="span" sx={{ color: T.num }}>
          {value}
        </Box>
        {tail}
      </>
    );
  if (typeof value === 'string')
    return (
      <>
        <Box component="span" sx={{ color: T.str }}>
          &quot;{value}&quot;
        </Box>
        {tail}
      </>
    );

  if (Array.isArray(value)) {
    if (!value.length)
      return (
        <>
          <Box component="span" sx={{ color: T.bracket }}>
            []
          </Box>
          {tail}
        </>
      );
    return (
      <>
        <Box component="span" sx={{ color: T.bracket }}>
          {'['}
        </Box>
        {'\n'}
        {value.map((item, i) => (
          // eslint-disable-next-line react/no-array-index-key
          <Fragment key={`${path}[${i}]`}>
            {indent(depth + 1)}
            <JsonPreview
              value={item}
              path={`${path}[${i}]`}
              depth={depth + 1}
              comma={i < value.length - 1}
              pathToVar={pathToVar}
              onKeyClick={onKeyClick}
            />
            {'\n'}
          </Fragment>
        ))}
        {indent(depth)}
        <Box component="span" sx={{ color: T.bracket }}>
          {']'}
        </Box>
        {tail}
      </>
    );
  }

  if (typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>);
    if (!entries.length)
      return (
        <>
          <Box component="span" sx={{ color: T.bracket }}>
            {'{}'}
          </Box>
          {tail}
        </>
      );
    return (
      <>
        <Box component="span" sx={{ color: T.bracket }}>
          {'{'}
        </Box>
        {'\n'}
        {entries.map(([k, v], i) => {
          const childPath = path ? `${path}.${k}` : k;
          const isAlreadyMapped = pathToVar[childPath] !== undefined;
          return (
            <Fragment key={k}>
              {indent(depth + 1)}
              <Box
                component="span"
                onClick={
                  onKeyClick
                    ? e => onKeyClick(childPath, e.currentTarget as HTMLElement)
                    : undefined
                }
                sx={{
                  color: isAlreadyMapped ? 'primary.main' : T.key,
                  fontWeight: isAlreadyMapped ? 600 : 400,
                  ...(onKeyClick && {
                    cursor: 'pointer',
                    borderRadius: '2px',
                    px: '2px',
                    ml: '-2px',
                    '&:hover': {
                      bgcolor: (t: Theme) => alpha(t.palette.primary.main, 0.1),
                      outline: '1px dashed',
                      outlineColor: 'primary.main',
                    },
                  }),
                }}
              >
                &quot;{k}&quot;
              </Box>
              <Box component="span" sx={{ color: T.comma }}>
                :{' '}
              </Box>
              <JsonPreview
                value={v}
                path={childPath}
                depth={depth + 1}
                comma={i < entries.length - 1}
                pathToVar={pathToVar}
                onKeyClick={onKeyClick}
              />
              {'\n'}
            </Fragment>
          );
        })}
        {indent(depth)}
        <Box component="span" sx={{ color: T.bracket }}>
          {'}'}
        </Box>
        {tail}
      </>
    );
  }

  return null;
}

// ── Template preview ──────────────────────────────────────────────────────────

export function TemplatePreview({ template }: { template: string }) {
  const parts = template.split(/(\{\{[^}]+\}\})/g);
  return (
    <>
      {parts.map((part, i) =>
        /^\{\{[^}]+\}\}$/.test(part) ? (
          // eslint-disable-next-line react/no-array-index-key
          <Box key={i} component="span" sx={varChipSx}>
            {part}
          </Box>
        ) : (
          part
        )
      )}
    </>
  );
}

// ── responseMapping → pathToVar ───────────────────────────────────────────────
// { "output": "$.choices[0].message.content" } → { "choices[0].message.content": "output" }

export function responseMappingToPathToVar(
  responseMapping: Record<string, string>
): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [varName, jsonPath] of Object.entries(responseMapping)) {
    const cleaned = jsonPath.replace(/^\$\.?/, '');
    if (cleaned) out[cleaned] = varName;
  }
  return out;
}

// ── pathToVar → responseMapping ───────────────────────────────────────────────

export function pathToVarToResponseMapping(
  pathToVar: Record<string, string>
): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [path, varName] of Object.entries(pathToVar)) {
    out[varName] = `$.${path}`;
  }
  return out;
}
