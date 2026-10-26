'use client';

import React, { useRef, useState } from 'react';
import { Box, TextField, Typography } from '@mui/material';
import { useTheme } from '@mui/material/styles';
import { BORDER_RADIUS } from '@/styles/theme';
import JsonMonacoField from '../[identifier]/components/JsonMonacoField';
import {
  MappingColumnHeaders,
  MappingRow,
  MappingRowList,
  ModeLink,
} from './MappingRows';
import { formatTestValue, isFileVar, type TestValues } from './testValues';

interface TestValuesEditorProps {
  /** Variables to ask for, in display order; file variables need renderFileField. */
  vars: string[];
  values: TestValues;
  onValuesChange: (values: TestValues) => void;
  editorKey: string;
  /** Accessible name of a row's field. */
  fieldLabel?: (name: string) => string;
  /** Show only the JSON editor, without the switch back to one field per variable. */
  jsonOnly?: boolean;
  /** Upload control for a file variable; without it file variables are left out. */
  renderFileField?: (name: string) => React.ReactNode;
}

const EDITOR_LINE_PX = 20;
const EDITOR_PADDING_PX = 16;
const MIN_EDITOR_PX = 3 * EDITOR_LINE_PX + EDITOR_PADDING_PX;

/** Fits the editor to its JSON, between 3 and 12 lines, so a short value leaves no empty block. */
function editorHeight(json: string): string {
  const lines = Math.min(Math.max(json.split('\n').length, 3), 12);
  return `${lines * EDITOR_LINE_PX + EDITOR_PADDING_PX}px`;
}

/** One text field per variable, or the values as JSON for anything that isn't plain text. */
export default function TestValuesEditor({
  vars,
  values,
  onValuesChange,
  editorKey,
  fieldLabel = name => `Value for ${name}`,
  jsonOnly = false,
  renderFileField,
}: TestValuesEditorProps) {
  const theme = useTheme();
  const editorTheme = theme.palette.mode === 'dark' ? 'vs-dark' : 'light';

  const shownVars = renderFileField ? vars : vars.filter(v => !isFileVar(v));
  const textVars = shownVars.filter(v => !isFileVar(v));
  const fileVars = shownVars.filter(isFileVar);

  const toJson = () =>
    JSON.stringify(
      Object.fromEntries(textVars.map(v => [v, values[v] ?? ''])),
      null,
      2
    );

  // Set once the user drags the bar under the editor; until then it fits its content.
  const [dragHeight, setDragHeight] = useState<number | null>(null);
  const editorBoxRef = useRef<HTMLDivElement>(null);

  const startDrag = (e: React.PointerEvent<HTMLElement>) => {
    const bar = e.currentTarget;
    const startY = e.clientY;
    const startHeight = editorBoxRef.current?.offsetHeight ?? 0;
    bar.setPointerCapture(e.pointerId);
    const move = (ev: PointerEvent) =>
      setDragHeight(Math.max(MIN_EDITOR_PX, startHeight + ev.clientY - startY));
    const end = () => {
      bar.removeEventListener('pointermove', move);
      bar.removeEventListener('pointerup', end);
    };
    bar.addEventListener('pointermove', move);
    bar.addEventListener('pointerup', end);
  };

  const handleResizeKey = (e: React.KeyboardEvent<HTMLElement>) => {
    if (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') return;
    e.preventDefault();
    const current = editorBoxRef.current?.offsetHeight ?? 0;
    const step = e.key === 'ArrowDown' ? EDITOR_LINE_PX : -EDITOR_LINE_PX;
    setDragHeight(Math.max(MIN_EDITOR_PX, current + step));
  };

  const [mode, setMode] = useState<'rows' | 'json'>(jsonOnly ? 'json' : 'rows');
  const [valuesJson, setValuesJson] = useState(() =>
    jsonOnly ? toJson() : ''
  );

  // Test runs only ever pass text here, so another type would test a request they never send.
  const inputNotText =
    values.input !== undefined && typeof values.input !== 'string';

  const allStrings = textVars.every(
    v => values[v] === undefined || typeof values[v] === 'string'
  );

  const openJson = () => {
    setValuesJson(toJson());
    setMode('json');
  };

  const handleJsonChange = (text: string) => {
    setValuesJson(text);
    try {
      const parsed: unknown = JSON.parse(text);
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
        onValuesChange(parsed as TestValues);
      }
    } catch {
      // Keep the last valid values while the JSON is mid-edit.
    }
  };

  if (mode === 'json') {
    return (
      <>
        <Box>
          <Box ref={editorBoxRef}>
            <JsonMonacoField
              editorKey={editorKey}
              height={
                dragHeight !== null
                  ? `${dragHeight}px`
                  : editorHeight(valuesJson)
              }
              theme={editorTheme}
              value={valuesJson}
              onChange={handleJsonChange}
            />
          </Box>
          <Box
            role="separator"
            aria-orientation="horizontal"
            aria-label="Resize editor"
            tabIndex={0}
            onPointerDown={startDrag}
            onKeyDown={handleResizeKey}
            sx={{
              height: theme.spacing(1.5),
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'ns-resize',
              touchAction: 'none',
              '&:hover > span, &:focus-visible > span': {
                bgcolor: 'text.secondary',
              },
            }}
          >
            <Box
              component="span"
              sx={{
                width: theme.spacing(5),
                height: theme.spacing(0.5),
                borderRadius: BORDER_RADIUS.pill,
                bgcolor: 'divider',
              }}
            />
          </Box>
          <Typography
            variant="caption"
            color={inputNotText ? 'error' : 'text.secondary'}
            component="p"
            sx={{ mt: 0.5, mx: 1.75 }}
          >
            {inputNotText ? (
              <>
                Test runs always send <code>input</code> as text. For JSON
                input, put the JSON in a string and add <code>| fromjson</code>{' '}
                to the mapping.
              </>
            ) : (
              <>
                One key per variable. <code>input</code> is text, as in test
                runs; <code>messages</code> is a list of{' '}
                <code>{'{ role, content }'}</code> objects.
              </>
            )}
          </Typography>
        </Box>
        {renderFileField && fileVars.length > 0 && (
          <MappingRowList>
            {fileVars.map(v => (
              <MappingRow key={v} label={v}>
                {renderFileField(v)}
              </MappingRow>
            ))}
          </MappingRowList>
        )}
        {!jsonOnly && (
          <ModeLink
            disabled={!allStrings}
            disabledReason="Easy input only works when every value is text."
            onClick={() => setMode('rows')}
          >
            Switch to easy input
          </ModeLink>
        )}
      </>
    );
  }

  return (
    <>
      {shownVars.length > 0 ? (
        <Box>
          <MappingColumnHeaders left="Rhesis' variables" right="Test value" />
          <MappingRowList>
            {shownVars.map(v => (
              <MappingRow key={v} label={v}>
                {renderFileField && isFileVar(v) ? (
                  renderFileField(v)
                ) : (
                  <TextField
                    fullWidth
                    size="small"
                    multiline
                    maxRows={4}
                    placeholder="Type a test value"
                    value={formatTestValue(values[v] ?? '')}
                    onChange={e =>
                      onValuesChange({ ...values, [v]: e.target.value })
                    }
                    slotProps={{
                      htmlInput: { 'aria-label': fieldLabel(v) },
                    }}
                  />
                )}
              </MappingRow>
            ))}
          </MappingRowList>
        </Box>
      ) : (
        <Typography variant="body2" color="text.secondary">
          The request uses no variables, so there is nothing to fill in.
        </Typography>
      )}
      {textVars.length > 0 && (
        <ModeLink onClick={openJson}>Edit as JSON</ModeLink>
      )}
    </>
  );
}
