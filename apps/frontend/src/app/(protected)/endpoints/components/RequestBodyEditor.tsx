'use client';

import React, { useRef, useEffect } from 'react';
import {
  Box,
  Chip,
  Menu,
  MenuItem,
  Typography,
  CircularProgress,
} from '@mui/material';
import dynamic from 'next/dynamic';
import type { OnMount, BeforeMount } from '@monaco-editor/react';
import { useTheme } from '@mui/material/styles';
import { editorContainerSx, insertableVariableChipSx } from './endpoint-styles';

// Injected once — colors {{ ... }} template tokens inline inside Monaco
const DECORATION_CSS_ID = 'rhesis-template-decoration-css';
function ensureDecorationCss(primaryColor: string) {
  if (typeof document === 'undefined') return;
  let el = document.getElementById(DECORATION_CSS_ID);
  if (!el) {
    el = document.createElement('style');
    el.id = DECORATION_CSS_ID;
    document.head.appendChild(el);
  }
  el.textContent = `
    .rhesis-tpl-var {
      background-color: color-mix(in srgb, ${primaryColor} 14%, transparent);
      color: ${primaryColor} !important;
      border-radius: 3px;
    }
  `;
}

const MonacoEditor = dynamic(() => import('@monaco-editor/react'), {
  ssr: false,
  loading: () => (
    <Box
      sx={{
        ...editorContainerSx,
        height: 200,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <CircularProgress size={20} />
        <Typography variant="body2" color="text.secondary">
          Loading editor…
        </Typography>
      </Box>
    </Box>
  ),
});

const MESSAGES_PROVIDERS = [
  {
    label: 'OpenAI',
    value: '{{ messages | tojson }}',
    hint: 'Standard [{role, content}] format used by OpenAI and Anthropic',
  },
  {
    label: 'Anthropic',
    value: '{{ messages | to_anthropic_messages | tojson }}',
    hint: 'Strips system message from array (pass system separately)',
  },
  {
    label: 'Gemini',
    value: '{{ messages | to_gemini_contents | tojson }}',
    hint: 'Converts to [{role, parts: [{text}]}] format for Gemini',
  },
];

const FILES_PROVIDERS = [
  {
    label: 'OpenAI',
    value: '"{{ files | to_openai | tojson }}"',
    hint: 'Spreads image_url parts into a content array alongside {{ input }}',
  },
  {
    label: 'Anthropic',
    value: '"{{ files | to_anthropic | tojson }}"',
    hint: 'Spreads image/document parts into a content array alongside {{ input }}',
  },
  {
    label: 'Gemini',
    value: '"{{ files | to_gemini | tojson }}"',
    hint: 'Spreads inline_data parts into a parts array alongside {{ input }}',
  },
];

interface Variable {
  /** Single chip — use this OR chips, not both */
  name?: string;
  /** Multiple chips rendered in one row, sharing the description below */
  chips?: string[];
  /** Optional label shown above the chip(s) to name a group */
  groupLabel?: string;
  required?: boolean;
  description?: React.ReactNode;
  docsUrl?: string;
}

interface Props {
  value: string;
  onChange: (value: string) => void;
  variables: Variable[];
  layout?: 'top' | 'side' | 'bottom';
}

type MonacoInstance = Parameters<BeforeMount>[0];
type EditorInstance = Parameters<OnMount>[0];

export default function RequestBodyEditor({
  value,
  onChange,
  variables,
  layout = 'top',
}: Props) {
  const theme = useTheme();
  const editorTheme = theme.palette.mode === 'dark' ? 'vs-dark' : 'light';

  const editorRef = useRef<EditorInstance | null>(null);
  const monacoRef = useRef<MonacoInstance | null>(null);
  const decorationsRef = useRef<string[]>([]);
  const [filesAnchor, setFilesAnchor] = React.useState<null | HTMLElement>(
    null
  );
  const [messagesAnchor, setMessagesAnchor] =
    React.useState<null | HTMLElement>(null);

  // Keep decoration CSS in sync with theme primary colour
  useEffect(() => {
    ensureDecorationCss(theme.palette.primary.main);
  }, [theme.palette.primary.main]);

  const updateDecorations = (
    editor: EditorInstance,
    monaco: MonacoInstance
  ) => {
    const model = editor.getModel();
    if (!model) return;
    const text = model.getValue();
    const newDecorations: Parameters<typeof editor.deltaDecorations>[1] = [];
    const re = /\{\{[^}]+\}\}/g;
    let m: RegExpExecArray | null;
    while ((m = re.exec(text)) !== null) {
      const start = model.getPositionAt(m.index);
      const end = model.getPositionAt(m.index + m[0].length);
      newDecorations.push({
        range: new monaco.Range(
          start.lineNumber,
          start.column,
          end.lineNumber,
          end.column
        ),
        options: { inlineClassName: 'rhesis-tpl-var' },
      });
    }
    decorationsRef.current = editor.deltaDecorations(
      decorationsRef.current,
      newDecorations
    );
  };

  const handleBeforeMount: BeforeMount = monaco => {
    monacoRef.current = monaco;
  };

  const handleMount: OnMount = (editor, monaco) => {
    editorRef.current = editor;
    monacoRef.current = monaco;

    // Silence JSON validation — the template expressions ({{ ... }}) make the
    // content technically invalid JSON until rendered, but that's intentional.
    monaco.languages.json.jsonDefaults.setDiagnosticsOptions({
      validate: false,
    });

    updateDecorations(editor, monaco);
    editor.onDidChangeModelContent(() => {
      const v = editor.getValue();
      onChange(v);
      updateDecorations(editor, monaco);
    });
  };

  const insertAtCursor = (text: string) => {
    setFilesAnchor(null);
    const editor = editorRef.current;
    const monaco = monacoRef.current;
    if (!editor || !monaco) {
      onChange(value + text);
      return;
    }
    const position = editor.getPosition();
    if (!position) {
      onChange(value + text);
      return;
    }
    editor.executeEdits('insert-var', [
      {
        range: new monaco.Range(
          position.lineNumber,
          position.column,
          position.lineNumber,
          position.column
        ),
        text,
      },
    ]);
    // Place cursor after inserted text
    const newCol = position.column + text.length;
    editor.setPosition({ lineNumber: position.lineNumber, column: newCol });
    editor.focus();
  };

  // Variables that render to a plain string and must be quoted in JSON
  const STRING_VARS = new Set([
    '{{ input }}',
    '{{ system_prompt }}',
    '{{ conversation_id }}',
  ]);

  const handleChipClick = (name: string, e: React.MouseEvent<HTMLElement>) => {
    if (name === '{{ files }}') {
      setFilesAnchor(e.currentTarget);
    } else if (name === '{{ messages }}') {
      setMessagesAnchor(e.currentTarget);
    } else if (STRING_VARS.has(name)) {
      insertAtCursor(`"${name}"`);
    } else {
      insertAtCursor(name);
    }
  };

  const chipLabel = (name: string) =>
    name === '{{ files }}' || name === '{{ messages }}' ? `${name} ▾` : name;

  const editor = (
    <Box
      sx={{
        ...editorContainerSx,
        '&:focus-within': {
          outline: '2px solid',
          outlineColor: 'primary.main',
          outlineOffset: '-1px',
        },
        flex: layout === 'side' ? 1 : undefined,
        flexShrink: layout === 'bottom' ? 0 : undefined,
      }}
    >
      <MonacoEditor
        key={`req-body-editor-${editorTheme}`}
        height="220px"
        defaultLanguage="json"
        theme={editorTheme}
        value={value}
        beforeMount={handleBeforeMount}
        onMount={handleMount}
        options={{
          minimap: { enabled: false },
          lineNumbers: 'off',
          scrollBeyondLastLine: false,
          automaticLayout: true,
          padding: { top: 8, bottom: 8 },
          fontSize: 13,
          wordWrap: 'on',
          tabSize: 2,
          formatOnType: true,
          formatOnPaste: true,
        }}
      />
    </Box>
  );

  const variableColumn = (variable: Variable, i: number) => {
    const names = variable.chips ?? (variable.name ? [variable.name] : []);
    const { groupLabel, description, docsUrl } = variable;
    return (
      <Box
        // eslint-disable-next-line react/no-array-index-key
        key={i}
        sx={{
          display: 'flex',
          flexDirection: 'column',
          gap: 0.5,
          p: 1.5,
          borderRadius: 1,
          bgcolor: theme => theme.palette.greyscale.fieldSurface,
        }}
      >
        {groupLabel && (
          <Typography
            variant="caption"
            sx={{ color: 'text.secondary', fontSize: 11, fontWeight: 600 }}
          >
            {groupLabel}
          </Typography>
        )}
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
          {names.map(name => (
            <Chip
              key={name}
              label={chipLabel(name)}
              size="small"
              onClick={e => handleChipClick(name, e)}
              sx={{ ...insertableVariableChipSx, alignSelf: 'flex-start' }}
            />
          ))}
        </Box>
        {(description || docsUrl) && (
          <Typography
            variant="caption"
            sx={{ color: 'text.disabled', fontSize: 10, lineHeight: 1.4 }}
          >
            {description}
            {docsUrl && (
              <>
                {' '}
                <Box
                  component="a"
                  href={docsUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  sx={{
                    color: 'primary.main',
                    textDecoration: 'none',
                    '&:hover': { textDecoration: 'underline' },
                  }}
                >
                  Docs ↗
                </Box>
              </>
            )}
          </Typography>
        )}
      </Box>
    );
  };

  const chipsPanel =
    layout === 'side' ? (
      <Box
        sx={{
          width: 220,
          flexShrink: 0,
          display: 'flex',
          flexDirection: 'column',
          gap: 1,
          pl: 1.5,
        }}
      >
        {variables.map((variable, i) => {
          const names =
            variable.chips ?? (variable.name ? [variable.name] : []);
          const { groupLabel, description, docsUrl } = variable;
          return (
            <Box
              // eslint-disable-next-line react/no-array-index-key
              key={i}
              sx={{ display: 'flex', flexDirection: 'column', gap: 0.25 }}
            >
              {groupLabel && (
                <Typography
                  variant="caption"
                  sx={{
                    color: 'text.secondary',
                    fontSize: 10,
                    fontWeight: 600,
                    pl: 0.25,
                  }}
                >
                  {groupLabel}
                </Typography>
              )}
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                {names.map(name => (
                  <Chip
                    key={name}
                    label={chipLabel(name)}
                    size="small"
                    onClick={e => handleChipClick(name, e)}
                    sx={{
                      ...insertableVariableChipSx,
                      alignSelf: 'flex-start',
                    }}
                  />
                ))}
              </Box>
              {(description || docsUrl) && (
                <Typography
                  variant="caption"
                  sx={{
                    color: 'text.disabled',
                    fontSize: 10,
                    lineHeight: 1.4,
                    pl: 0.25,
                  }}
                >
                  {description}
                  {docsUrl && (
                    <>
                      {' '}
                      <Box
                        component="a"
                        href={docsUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        sx={{
                          color: 'primary.main',
                          textDecoration: 'none',
                          '&:hover': { textDecoration: 'underline' },
                        }}
                      >
                        Docs ↗
                      </Box>
                    </>
                  )}
                </Typography>
              )}
            </Box>
          );
        })}
      </Box>
    ) : (
      <Box
        sx={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 0.5,
          mb: 1,
          alignItems: 'center',
        }}
      >
        {variables.flatMap((variable, i) =>
          (variable.chips ?? (variable.name ? [variable.name] : [])).map(
            name => (
              <Chip
                // eslint-disable-next-line react/no-array-index-key
                key={`${i}-${name}`}
                label={chipLabel(name)}
                size="small"
                onClick={e => handleChipClick(name, e)}
                sx={insertableVariableChipSx}
              />
            )
          )
        )}
      </Box>
    );

  return (
    <Box>
      {layout === 'top' && chipsPanel}
      <Box
        sx={
          layout === 'side'
            ? { display: 'flex', alignItems: 'flex-start' }
            : undefined
        }
      >
        {editor}
        {layout === 'side' && chipsPanel}
      </Box>
      {layout === 'bottom' && (
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            gap: 1,
            mt: 1.5,
          }}
        >
          {variables.map((variable, i) => variableColumn(variable, i))}
        </Box>
      )}

      <Menu
        anchorEl={filesAnchor}
        open={Boolean(filesAnchor)}
        onClose={() => setFilesAnchor(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
        slotProps={{ paper: { sx: { minWidth: 220 } } }}
      >
        <Typography
          variant="caption"
          sx={{
            px: 2,
            py: 0.5,
            display: 'block',
            color: 'text.disabled',
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
          }}
        >
          Provider format
        </Typography>
        {FILES_PROVIDERS.map(({ label, value: v, hint }) => (
          <MenuItem
            key={label}
            onClick={() => insertAtCursor(v)}
            sx={{ fontSize: 12 }}
          >
            <Box>
              <Typography variant="body2" sx={{ fontSize: 12 }}>
                {label}
              </Typography>
              <Typography
                variant="caption"
                sx={{
                  fontFamily: 'monospace',
                  fontSize: 10,
                  color: 'text.disabled',
                  display: 'block',
                }}
              >
                {v}
              </Typography>
              <Typography
                variant="caption"
                sx={{ fontSize: 10, color: 'text.disabled' }}
              >
                {hint}
              </Typography>
            </Box>
          </MenuItem>
        ))}
      </Menu>

      <Menu
        anchorEl={messagesAnchor}
        open={Boolean(messagesAnchor)}
        onClose={() => setMessagesAnchor(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
        slotProps={{ paper: { sx: { minWidth: 260 } } }}
      >
        <Typography
          variant="caption"
          sx={{
            px: 2,
            py: 0.5,
            display: 'block',
            color: 'text.disabled',
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
          }}
        >
          Provider format
        </Typography>
        {MESSAGES_PROVIDERS.map(({ label, value: v, hint }) => (
          <MenuItem
            key={label}
            onClick={() => {
              setMessagesAnchor(null);
              insertAtCursor(v);
            }}
            sx={{ fontSize: 12 }}
          >
            <Box>
              <Typography variant="body2" sx={{ fontSize: 12 }}>
                {label}
              </Typography>
              <Typography
                variant="caption"
                sx={{
                  fontFamily: 'monospace',
                  fontSize: 10,
                  color: 'text.disabled',
                  display: 'block',
                }}
              >
                {v}
              </Typography>
              <Typography
                variant="caption"
                sx={{ fontSize: 10, color: 'text.disabled' }}
              >
                {hint}
              </Typography>
            </Box>
          </MenuItem>
        ))}
      </Menu>
    </Box>
  );
}
