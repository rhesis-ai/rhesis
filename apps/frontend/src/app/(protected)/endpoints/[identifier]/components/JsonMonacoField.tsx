'use client';

import { useEffect, useRef } from 'react';
import dynamic from 'next/dynamic';
import { Box, CircularProgress, Typography } from '@mui/material';
import { useTheme } from '@mui/material/styles';
import type { OnMount } from '@monaco-editor/react';
import { BORDER_RADIUS } from '@/styles/theme-constants';

// Shared CSS id with RequestBodyEditor / HeadersEditor
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

const Editor = dynamic(() => import('@monaco-editor/react'), {
  ssr: false,
  loading: () => (
    <Box
      sx={{
        height: '200px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        border: 1,
        borderColor: 'divider',
        borderRadius: BORDER_RADIUS.sm,
        backgroundColor: 'background.default',
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

interface JsonMonacoFieldProps {
  editorKey: string;
  height: string;
  theme: string;
  value: string;
  readOnly?: boolean;
  wrapperSx: object;
  onChange?: (value: string) => void;
}

export default function JsonMonacoField({
  editorKey,
  height,
  theme,
  value,
  readOnly = false,
  wrapperSx,
  onChange,
}: JsonMonacoFieldProps) {
  const muiTheme = useTheme();
  const editorRef = useRef<Parameters<OnMount>[0] | null>(null);
  const monacoRef = useRef<Parameters<OnMount>[1] | null>(null);
  const decorationsRef = useRef<string[]>([]);

  useEffect(() => {
    ensureDecorationCss(muiTheme.palette.primary.main);
  }, [muiTheme.palette.primary.main]);

  const updateDecorations = (
    editor: Parameters<OnMount>[0],
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

  const handleMount: OnMount = (editor, monaco) => {
    editorRef.current = editor;
    monacoRef.current = monaco;
    updateDecorations(editor, monaco);
    editor.onDidChangeModelContent(() => updateDecorations(editor, monaco));
  };

  return (
    <Box sx={{ ...wrapperSx, height, minHeight: height }}>
      <Editor
        key={`${editorKey}-${theme}`}
        height={height}
        defaultLanguage="plaintext"
        theme={theme}
        value={value}
        onMount={handleMount}
        onChange={v => onChange?.(v || '')}
        options={{
          readOnly,
          minimap: { enabled: false },
          lineNumbers: 'on',
          scrollBeyondLastLine: true,
          padding: { bottom: 8 },
          folding: !readOnly,
          automaticLayout: true,
          wordWrap: 'on',
        }}
      />
    </Box>
  );
}
