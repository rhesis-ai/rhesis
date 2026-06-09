'use client';

import React from 'react';
import {
  Box,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Select,
  MenuItem,
  IconButton,
  InputAdornment,
  Typography,
} from '@mui/material';
import { DeleteIcon } from '@/components/icons';
import { HelpTooltip } from '@/components/common/HelpTooltip';
import TemplateVariableInput from './TemplateVariableInput';

export interface MappingRow {
  api: string;
  rhesis: string;
  def?: string;
  required?: boolean;
}

interface MappingTableProps {
  rows: MappingRow[];
  onChange: React.Dispatch<React.SetStateAction<MappingRow[]>>;
  rhesisVars: string[];
  showDefault: boolean;
  /** Use the template editor (free text + atomic {{ }} chips) instead of a plain Select */
  templateMode?: boolean;
  /** Flip columns: your API field on the left, Rhesis variable on the right */
  reversed?: boolean;
}

const JSONPATH_TOOLTIP = (
  <Box sx={{ p: 0.5 }}>
    <Typography
      variant="caption"
      sx={{ fontWeight: 600, display: 'block', mb: 0.5 }}
    >
      JSONPath expression
    </Typography>
    <Typography variant="caption" sx={{ display: 'block', mb: 0.5 }}>
      Use{' '}
      <Box component="span" sx={{ fontFamily: 'monospace' }}>
        $.
      </Box>{' '}
      to navigate into the JSON your API returns.
    </Typography>
    <Typography
      variant="caption"
      sx={{ fontFamily: 'monospace', display: 'block', opacity: 0.75 }}
    >
      $.output
    </Typography>
    <Typography
      variant="caption"
      sx={{ fontFamily: 'monospace', display: 'block', opacity: 0.75 }}
    >
      $.choices[0].message.content
    </Typography>
    <Typography
      variant="caption"
      sx={{ fontFamily: 'monospace', display: 'block', opacity: 0.75 }}
    >
      $.data.response.text
    </Typography>
  </Box>
);

function isParams(v: string) {
  return v.startsWith('{{ params.');
}

export default function MappingTable({
  rows,
  onChange,
  rhesisVars,
  showDefault,
  templateMode = false,
  reversed = false,
}: MappingTableProps) {
  const hasDefault = showDefault && rows.some(r => isParams(r.rhesis));

  const updateRow = (i: number, field: keyof MappingRow, value: string) => {
    onChange(prev =>
      prev.map((r, idx) =>
        idx === i
          ? {
              ...r,
              [field]: value,
              ...(field === 'rhesis' && !isParams(value) ? { def: '' } : {}),
            }
          : r
      )
    );
  };

  const removeRow = (i: number) =>
    onChange(prev => prev.filter((_, idx) => idx !== i));

  return (
    <Table size="small" sx={{ tableLayout: 'fixed' }}>
      <TableHead>
        <TableRow>
          <TableCell
            sx={{
              color: 'text.disabled',
              fontSize: 10,
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              pb: 0.5,
              pl: 0,
            }}
          >
            {reversed ? (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                From your API response
                <HelpTooltip title={JSONPATH_TOOLTIP} />
              </Box>
            ) : (
              'Key'
            )}
          </TableCell>
          <TableCell sx={{ width: 24 }} />
          <TableCell
            sx={{
              color: 'text.disabled',
              fontSize: 10,
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              pb: 0.5,
            }}
          >
            {reversed ? 'Rhesis field' : 'Value'}
          </TableCell>
          {hasDefault && (
            <TableCell
              sx={{
                color: 'text.disabled',
                fontSize: 10,
                letterSpacing: '0.08em',
                textTransform: 'uppercase',
                pb: 0.5,
                width: 90,
              }}
            >
              Default
            </TableCell>
          )}
          <TableCell sx={{ width: 32 }} />
        </TableRow>
      </TableHead>
      <TableBody>
        {rows.map((row, i) => (
          // eslint-disable-next-line react/no-array-index-key
          <TableRow key={i}>
            <TableCell sx={{ pl: 0, py: 0.5 }}>
              {reversed ? (
                <TextField
                  size="small"
                  value={row.api}
                  onChange={e => updateRow(i, 'api', e.target.value)}
                  placeholder="my-response"
                  InputProps={{
                    startAdornment: (
                      <InputAdornment
                        position="start"
                        sx={{
                          fontFamily: 'monospace',
                          fontSize: 12,
                          color: 'text.secondary',
                          userSelect: 'none',
                          mr: 0,
                        }}
                      >
                        $.
                      </InputAdornment>
                    ),
                  }}
                  inputProps={{
                    style: { fontFamily: 'monospace', fontSize: 12 },
                  }}
                  fullWidth
                />
              ) : (
                <TextField
                  size="small"
                  value={row.api}
                  onChange={e => updateRow(i, 'api', e.target.value)}
                  placeholder="body-key"
                  inputProps={{
                    style: { fontFamily: 'monospace', fontSize: 12 },
                  }}
                  fullWidth
                />
              )}
            </TableCell>
            <TableCell
              sx={{
                textAlign: 'center',
                color: 'text.disabled',
                py: 0.5,
                fontSize: 12,
              }}
            >
              →
            </TableCell>
            <TableCell sx={{ py: 0.5 }}>
              {reversed ? (
                <Select
                  size="small"
                  value={
                    rhesisVars.includes(row.rhesis)
                      ? row.rhesis
                      : row.rhesis || rhesisVars[0]
                  }
                  onChange={e => updateRow(i, 'rhesis', e.target.value)}
                  fullWidth
                  sx={{ fontFamily: 'monospace', fontSize: 12 }}
                >
                  {(rhesisVars.includes(row.rhesis)
                    ? rhesisVars
                    : [row.rhesis, ...rhesisVars]
                  ).map(v => (
                    <MenuItem
                      key={v}
                      value={v}
                      sx={{ fontFamily: 'monospace', fontSize: 12 }}
                    >
                      {v}
                      {row.required && v === row.rhesis ? ' *' : ''}
                    </MenuItem>
                  ))}
                </Select>
              ) : templateMode ? (
                <TemplateVariableInput
                  value={row.rhesis}
                  onChange={val => updateRow(i, 'rhesis', val)}
                  variables={rhesisVars}
                />
              ) : (
                <Select
                  size="small"
                  value={
                    rhesisVars.includes(row.rhesis)
                      ? row.rhesis
                      : row.rhesis || rhesisVars[0]
                  }
                  onChange={e => updateRow(i, 'rhesis', e.target.value)}
                  fullWidth
                  sx={{ fontFamily: 'monospace', fontSize: 12 }}
                >
                  {(rhesisVars.includes(row.rhesis)
                    ? rhesisVars
                    : [row.rhesis, ...rhesisVars]
                  ).map(v => (
                    <MenuItem
                      key={v}
                      value={v}
                      sx={{ fontFamily: 'monospace', fontSize: 12 }}
                    >
                      {v}
                      {row.required && v === row.rhesis ? ' *' : ''}
                    </MenuItem>
                  ))}
                </Select>
              )}
            </TableCell>
            {hasDefault && (
              <TableCell sx={{ py: 0.5 }}>
                {isParams(row.rhesis) ? (
                  <TextField
                    size="small"
                    value={row.def || ''}
                    onChange={e => updateRow(i, 'def', e.target.value)}
                    placeholder="default"
                    inputProps={{
                      style: { fontFamily: 'monospace', fontSize: 12 },
                    }}
                    fullWidth
                  />
                ) : null}
              </TableCell>
            )}
            <TableCell sx={{ py: 0.5, pr: 0 }}>
              {row.required ? (
                <Box sx={{ width: 28 }} />
              ) : (
                <IconButton
                  size="small"
                  onClick={() => removeRow(i)}
                  sx={{ color: 'text.disabled' }}
                >
                  <DeleteIcon fontSize="small" />
                </IconButton>
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
