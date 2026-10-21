'use client';

import React, { useState } from 'react';
import { Box, TextField } from '@mui/material';
import { SectionCard } from '@/components/common/SectionCard';
import RequestBodyEditor from './RequestBodyEditor';
import { REQUEST_FIELDS, REQUEST_VARIABLES } from './mapping-variables';
import {
  CardSubtitle,
  MappingColumnHeaders,
  MappingRow,
  MappingRowList,
  ModeLink,
} from './MappingRows';
import {
  buildRequestTemplate,
  parseRequestTemplate,
  type RequestTemplateRows,
} from './requestTemplateRows';

interface RequestMappingCardProps {
  template: string;
  onChange: (template: string) => void;
}

export default function RequestMappingCard({
  template,
  onChange,
}: RequestMappingCardProps) {
  // A template easy input can't show opens in the editor, so a row edit can't overwrite it.
  const [mode, setMode] = useState<'rows' | 'json'>(() =>
    parseRequestTemplate(template) ? 'rows' : 'json'
  );
  // Rows keep their own state so two variables can briefly share a field while typing.
  const [rows, setRows] = useState<RequestTemplateRows>(
    () => parseRequestTemplate(template) ?? { fields: {}, systemPrompt: '' }
  );
  const { fields } = rows;

  const updateRows = (next: RequestTemplateRows) => {
    setRows(next);
    onChange(buildRequestTemplate(next));
  };

  const setField = (name: string, field: string) =>
    updateRows({
      ...rows,
      fields: { ...fields, [name]: { ...fields[name], field } },
    });

  const fieldCounts = new Map<string, number>();
  for (const { field } of Object.values(fields)) {
    const key = field.trim();
    if (key) fieldCounts.set(key, (fieldCounts.get(key) ?? 0) + 1);
  }

  const parsedForRows = mode === 'json' ? parseRequestTemplate(template) : null;

  return (
    <SectionCard
      title="Request"
      subtitle={
        <CardSubtitle>
          Tell Rhesis which field of your API&apos;s request body each variable
          goes into.
        </CardSubtitle>
      }
    >
      {mode === 'rows' ? (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <Box>
            <MappingColumnHeaders
              left="Rhesis' variables"
              right="Your API's fields"
            />
            <MappingRowList>
              {REQUEST_FIELDS.map(({ name, required, description }) => {
                const value = fields[name]?.field ?? '';
                const duplicate = (fieldCounts.get(value.trim()) ?? 0) > 1;
                return (
                  <MappingRow
                    key={name}
                    label={required ? `${name}*` : name}
                    info={description}
                  >
                    <TextField
                      fullWidth
                      size="small"
                      placeholder="Type in key value"
                      value={value}
                      onChange={e => setField(name, e.target.value)}
                      error={duplicate}
                      helperText={duplicate ? 'Used by another variable' : ''}
                      slotProps={{
                        htmlInput: { 'aria-label': `API field for ${name}` },
                      }}
                    />
                  </MappingRow>
                );
              })}
            </MappingRowList>
          </Box>
          <TextField
            fullWidth
            multiline
            minRows={2}
            label="System prompt (optional)"
            value={rows.systemPrompt}
            onChange={e =>
              updateRows({ ...rows, systemPrompt: e.target.value })
            }
            helperText="Sent as the system message in messages. For stateless endpoints Rhesis removes it from the body."
          />
          <ModeLink onClick={() => setMode('json')}>Edit as JSON</ModeLink>
        </Box>
      ) : (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <RequestBodyEditor
            value={template}
            onChange={onChange}
            variables={REQUEST_VARIABLES}
            layout="below"
          />
          <ModeLink
            disabled={!parsedForRows}
            disabledReason="Easy input only works with a flat body where each value is a single variable."
            onClick={() => {
              if (!parsedForRows) return;
              setRows(parsedForRows);
              setMode('rows');
            }}
          >
            Switch to easy input
          </ModeLink>
        </Box>
      )}
    </SectionCard>
  );
}
