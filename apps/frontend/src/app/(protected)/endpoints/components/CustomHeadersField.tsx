'use client';

import React, { useEffect, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  IconButton,
  Link,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import { AddIcon, DeleteIcon } from '@/components/icons';
import HeadersEditor from './HeadersEditor';
import {
  headerRowsToJson,
  newHeaderRow,
  parseHeaderRows,
  syncAuthorizationHeader,
  type HeaderRow,
} from './headerRows';
import { variableChipSx } from './endpoint-styles';

interface CustomHeadersFieldProps {
  /** Only a typed bearer token; an OAuth token never adds a header here. */
  authToken: string;
  requestHeaders: string;
  onChange: (value: string) => void;
  editorTheme: string;
}

/** Custom headers as key/value rows, with a switch to the raw JSON editor. */
export default function CustomHeadersField({
  authToken,
  requestHeaders,
  onChange,
  editorTheme,
}: CustomHeadersFieldProps) {
  // JSON that can't be shown as rows opens in the editor, so a row edit can't overwrite it.
  const [mode, setMode] = useState<'rows' | 'json'>(() =>
    parseHeaderRows(requestHeaders) ? 'rows' : 'json'
  );
  const [rows, setRows] = useState<HeaderRow[]>(() => {
    const parsed = parseHeaderRows(requestHeaders);
    return parsed && parsed.length > 0 ? parsed : [newHeaderRow()];
  });

  // HeadersEditor keeps the Authorization header in step with the token itself.
  useEffect(() => {
    if (mode !== 'rows') return;
    const next = syncAuthorizationHeader(requestHeaders, authToken);
    if (next === requestHeaders) return;
    onChange(next);
    setRows(parseHeaderRows(next) ?? [newHeaderRow()]);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- react to token changes only
  }, [authToken]);

  const updateRows = (next: HeaderRow[]) => {
    setRows(next);
    onChange(headerRowsToJson(next));
  };

  const updateRow = (id: string, field: 'key' | 'value', value: string) =>
    updateRows(rows.map(r => (r.id === id ? { ...r, [field]: value } : r)));

  const removeRow = (id: string) => {
    const next = rows.filter(r => r.id !== id);
    updateRows(next.length > 0 ? next : [newHeaderRow()]);
  };

  const parsedForRows = parseHeaderRows(requestHeaders);

  if (mode === 'json') {
    return (
      <Box>
        <HeadersEditor
          authToken={authToken}
          customHeaders={requestHeaders}
          onChange={onChange}
          editorTheme={editorTheme}
        />
        <Typography
          variant="caption"
          color="text.secondary"
          component="p"
          sx={{ mt: 0.5, mx: 1.75 }}
        >
          Use{' '}
          <Chip
            label="{{ auth_token }}"
            size="small"
            component="span"
            sx={{
              ...variableChipSx,
              height: 18,
              '& .MuiChip-label': { px: 0.75 },
            }}
          />{' '}
          in header values to reference the API token.
        </Typography>
        <Tooltip
          title={
            parsedForRows
              ? ''
              : 'Easy input only works with valid JSON whose values are all text.'
          }
        >
          <span>
            <Link
              component="button"
              type="button"
              variant="body1"
              disabled={!parsedForRows}
              onClick={() => {
                if (!parsedForRows) return;
                setRows(
                  parsedForRows.length > 0 ? parsedForRows : [newHeaderRow()]
                );
                setMode('rows');
              }}
              sx={{ mt: 2 }}
            >
              Switch to easy input
            </Link>
          </span>
        </Tooltip>
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      {rows.map(row => (
        <Box
          key={row.id}
          sx={{ display: 'flex', alignItems: 'center', gap: 3.75 }}
        >
          <TextField
            label="Key"
            value={row.key}
            onChange={e => updateRow(row.id, 'key', e.target.value)}
            sx={{ flex: 1 }}
          />
          <TextField
            label="Value"
            value={row.value}
            onChange={e => updateRow(row.id, 'value', e.target.value)}
            sx={{ flex: 2.75 }}
          />
          <IconButton
            aria-label={`Remove header ${row.key}`.trim()}
            onClick={() => removeRow(row.id)}
          >
            <DeleteIcon />
          </IconButton>
        </Box>
      ))}
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <Button
          startIcon={<AddIcon />}
          onClick={() => setRows([...rows, newHeaderRow()])}
          sx={{ px: 0.5 }}
        >
          Add header
        </Button>
        <Link
          component="button"
          type="button"
          variant="body1"
          onClick={() => setMode('json')}
        >
          Edit as JSON
        </Link>
      </Box>
    </Box>
  );
}
