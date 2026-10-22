'use client';

import React, { useState } from 'react';
import { Box, TextField } from '@mui/material';
import RequestBodyEditor from './RequestBodyEditor';
import { CREATE_REQUEST_VARIABLES, REQUEST_FIELDS } from './mapping-variables';
import {
  CardSubtitle,
  MappingCard,
  MappingColumnHeaders,
  MappingRow,
  MappingRowList,
  ModeLink,
} from './MappingRows';
import {
  buildRequestTemplate,
  conflictingFields,
  parseRequestTemplate,
  type RequestTemplateRows,
} from './requestTemplateRows';

interface RequestMappingCardProps {
  template: string;
  onChange: (template: string) => void;
  /** Header action, e.g. the button that sends the test request. */
  action?: React.ReactNode;
  complete?: boolean;
}

export default function RequestMappingCard({
  template,
  onChange,
  action,
  complete,
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

  const conflicts = conflictingFields(fields);

  const parsedForRows = mode === 'json' ? parseRequestTemplate(template) : null;

  return (
    <MappingCard
      title="Request"
      subtitle={
        <CardSubtitle>
          The field in your request body each variable goes into. Use dots for
          nested fields, e.g. <code>payload.query</code>. Leave unused rows
          empty.
        </CardSubtitle>
      }
      action={action}
      complete={complete}
    >
      {mode === 'rows' ? (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <Box>
            <MappingColumnHeaders
              left="Rhesis' variables"
              right="Field in your request body"
            />
            <MappingRowList>
              {REQUEST_FIELDS.map(({ name, required, description }) => {
                const value = fields[name]?.field ?? '';
                const duplicate = conflicts.has(name);
                return (
                  <MappingRow
                    key={name}
                    label={required ? `${name}*` : name}
                    info={description}
                  >
                    <TextField
                      fullWidth
                      size="small"
                      placeholder="e.g. prompt"
                      value={value}
                      onChange={e => setField(name, e.target.value)}
                      error={duplicate}
                      helperText={
                        duplicate ? 'Clashes with another variable' : ''
                      }
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
            variables={CREATE_REQUEST_VARIABLES}
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
    </MappingCard>
  );
}
