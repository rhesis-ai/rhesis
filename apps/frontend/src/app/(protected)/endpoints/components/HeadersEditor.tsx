'use client';

import React, { useEffect, useRef } from 'react';
import { Box, CircularProgress, Typography } from '@mui/material';
import { useTheme } from '@mui/material/styles';
import dynamic from 'next/dynamic';
import type { OnMount } from '@monaco-editor/react';
import { editorContainerSx } from './endpoint-styles';

// Shared with RequestBodyEditor — colours {{ ... }} tokens inside Monaco
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
        height: '140px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <CircularProgress size={20} />
        <Typography variant="body2" color="text.secondary">
          Loading editor...
        </Typography>
      </Box>
    </Box>
  ),
});

interface HeadersEditorProps {
  authToken: string;
  customHeaders: string;
  onChange: (customHeaders: string) => void;
  editorTheme: string;
}

const AUTH_TOKEN_PLACEHOLDER = '{{ auth_token }}';

function hasAuthTokenPlaceholder(obj: Record<string, unknown>): boolean {
  return Object.values(obj).some(
    v => typeof v === 'string' && /\{\{\s*auth_token\s*\}\}/.test(v)
  );
}

function buildInitialValue(authToken: string, customHeaders: string): string {
  let custom: Record<string, unknown> = {};
  try {
    custom = JSON.parse(customHeaders);
  } catch {
    /* keep empty */
  }

  // If customHeaders already references {{ auth_token }}, just show them as-is
  if (hasAuthTokenPlaceholder(custom)) {
    if (!('Content-Type' in custom)) {
      return JSON.stringify(
        { 'Content-Type': 'application/json', ...custom },
        null,
        2
      );
    }
    return JSON.stringify(custom, null, 2);
  }

  // No existing token reference — prepend Authorization if token is set
  const obj: Record<string, unknown> = {};
  if (authToken) obj['Authorization'] = `Bearer ${AUTH_TOKEN_PLACEHOLDER}`;
  if (!('Content-Type' in custom)) obj['Content-Type'] = 'application/json';
  Object.assign(obj, custom);
  return JSON.stringify(obj, null, 2);
}

type Editor = Parameters<OnMount>[0];

export default function HeadersEditor({
  authToken,
  customHeaders,
  onChange,
  editorTheme,
}: HeadersEditorProps) {
  const theme = useTheme();
  const editorRef = useRef<Editor | null>(null);
  const monacoRef = useRef<Parameters<OnMount>[1] | null>(null);
  const decorationsRef = useRef<string[]>([]);
  const authTokenRef = useRef(authToken);
  const customHeadersRef = useRef(customHeaders);
  const suppressRef = useRef(false);

  useEffect(() => {
    ensureDecorationCss(theme.palette.primary.main);
  }, [theme.palette.primary.main]);

  const updateDecorations = (
    editor: Editor,
    monaco: Parameters<OnMount>[1]
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

  authTokenRef.current = authToken;
  customHeadersRef.current = customHeaders;

  // When authToken is newly provided and no key already references {{ auth_token }},
  // prepend Authorization to the editor content.
  useEffect(() => {
    const editor = editorRef.current;
    if (!editor) return;
    const model = editor.getModel();
    if (!model) return;

    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(model.getValue()) as Record<string, unknown>;
    } catch {
      return;
    }

    const token = authToken;

    if (
      token &&
      !hasAuthTokenPlaceholder(parsed) &&
      !('Authorization' in parsed)
    ) {
      // Token just entered, no existing reference — add Authorization at top
      const next = JSON.stringify(
        { Authorization: `Bearer ${AUTH_TOKEN_PLACEHOLDER}`, ...parsed },
        null,
        2
      );
      suppressRef.current = true;
      const pos = editor.getPosition();
      model.pushEditOperations(
        [],
        [{ range: model.getFullModelRange(), text: next }],
        () => null
      );
      if (pos) editor.setPosition(pos);
      suppressRef.current = false;
      if (monacoRef.current) updateDecorations(editor, monacoRef.current);
      onChange(next);
    } else if (!token && 'Authorization' in parsed) {
      // Token cleared — remove Authorization
      const { Authorization: _drop, ...rest } = parsed;
      void _drop;
      const next = JSON.stringify(rest, null, 2);
      suppressRef.current = true;
      const pos = editor.getPosition();
      model.pushEditOperations(
        [],
        [{ range: model.getFullModelRange(), text: next }],
        () => null
      );
      if (pos) editor.setPosition(pos);
      suppressRef.current = false;
      if (monacoRef.current) updateDecorations(editor, monacoRef.current);
      onChange(next);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authToken]);

  const handleMount: OnMount = (editor, monaco) => {
    editorRef.current = editor;
    monacoRef.current = monaco;
    editor.setValue(
      buildInitialValue(authTokenRef.current, customHeadersRef.current)
    );
    updateDecorations(editor, monaco);

    editor.onDidChangeModelContent(() => {
      if (suppressRef.current) return;
      const model = editor.getModel();
      if (!model) return;
      updateDecorations(editor, monaco);
      try {
        JSON.parse(model.getValue()); // validate JSON before propagating
      } catch {
        return;
      }
      onChange(model.getValue());
    });
  };

  return (
    <Box
      sx={{
        ...editorContainerSx,
        '&:focus-within': {
          outline: '2px solid',
          outlineColor: 'primary.main',
          outlineOffset: '-1px',
        },
      }}
    >
      <MonacoEditor
        key={`headers-editor-${editorTheme}`}
        height="140px"
        defaultLanguage="plaintext"
        theme={editorTheme}
        onMount={handleMount}
        options={{
          minimap: { enabled: false },
          lineNumbers: 'off',
          scrollBeyondLastLine: false,
          automaticLayout: true,
          padding: { top: 8, bottom: 8 },
          fontSize: 13,
          wordWrap: 'on',
        }}
      />
    </Box>
  );
}
