'use client';

import dynamic from 'next/dynamic';
import { Box, CircularProgress, Typography } from '@mui/material';
import { BORDER_RADIUS } from '@/styles/theme-constants';

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
  return (
    <Box
      sx={{
        ...wrapperSx,
        height,
        minHeight: height,
      }}
    >
      <Editor
        key={`${editorKey}-${theme}`}
        height={height}
        defaultLanguage="json"
        theme={theme}
        value={value}
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
