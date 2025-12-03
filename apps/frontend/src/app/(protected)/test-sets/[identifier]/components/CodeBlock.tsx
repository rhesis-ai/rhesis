'use client';

import { useEffect, useRef, useState } from 'react';
import Prism from 'prismjs';
import 'prismjs/themes/prism-tomorrow.css';
import 'prismjs/components/prism-python';
// Additional Prism components for better Python highlighting
import 'prismjs/plugins/line-numbers/prism-line-numbers.css';
import 'prismjs/plugins/line-numbers/prism-line-numbers.js';
import { Paper, IconButton, Snackbar, useTheme } from '@mui/material';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';

export default function CodeBlock({ identifier }: { identifier: string }) {
  const [showCopyNotification, setShowCopyNotification] = useState(false);
  const codeRef = useRef<HTMLElement>(null);
  const [isClient, setIsClient] = useState(false);
  const theme = useTheme();

  const code = `from rhesis.entities import TestSet

# Initialize and load the test set
test_set = TestSet(id="${identifier}")
df = test_set.load()  # Returns a pandas DataFrame

# Alternatively, you can download the CSV file directly
test_set = TestSet(id="${identifier}")
test_set.download()  # Downloads to current directory as test_set_{id}.csv`;

  useEffect(() => {
    setIsClient(true);
  }, []);

  // Manually apply highlighting when the component is mounted
  useEffect(() => {
    if (isClient && codeRef.current && typeof window !== 'undefined') {
      // Prism is already imported at the top, just highlight the element
      Prism.highlightElement(codeRef.current);
    }
  }, [isClient]);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code);
    setShowCopyNotification(true);
  };

  return (
    <Paper
      variant="outlined"
      sx={{
        p: 2,
        bgcolor: theme.palette.mode === 'dark' ? 'grey.900' : 'grey.100',
        position: 'relative',
        borderRadius: '4px',
        '& pre, & code, & span': {
          margin: '0 !important',
          fontSize: '14px !important', // Slightly larger font
          lineHeight: '1.5 !important', // Better line height for readability
          fontFamily: '"Roboto Mono", "Fira Code", monospace !important',
        },
        '& pre': {
          backgroundColor: 'transparent !important',
          padding: theme.spacing(1, 0),
          overflow: 'auto',
        },
        '& code': {
          display: 'block',
          backgroundColor: 'transparent !important',
        },
        '& .token': {
          backgroundColor: 'transparent !important',
        },
        // Enhanced token colors for Python syntax
        '& .token.comment': {
          color: theme.palette.mode === 'dark' ? '#6A9955' : '#6A9955',
        },
        '& .token.string': {
          color: theme.palette.mode === 'dark' ? '#ce9178' : '#ce9178',
        },
        '& .token.keyword': {
          color: theme.palette.mode === 'dark' ? '#569cd6' : '#1976d2',
          fontWeight: '500 !important',
        },
        '& .token.function': {
          color: theme.palette.mode === 'dark' ? '#dcdcaa' : '#dcdcaa',
        },
        '& .token.class-name': {
          color: theme.palette.mode === 'dark' ? '#4EC9B0' : '#4EC9B0',
        },
        '& .token.operator': {
          color: theme.palette.mode === 'dark' ? '#d4d4d4' : '#424242',
        },
        '& .token.number': {
          color: theme.palette.mode === 'dark' ? '#b5cea8' : '#b5cea8',
        },
        '& .token.punctuation': {
          color: theme.palette.mode === 'dark' ? '#d4d4d4' : '#424242',
        },
        '& .token.builtin': {
          color: theme.palette.mode === 'dark' ? '#4EC9B0' : '#4EC9B0',
        },
        '& .token.important': {
          color: theme.palette.mode === 'dark' ? '#ff9d00' : '#ff9d00',
          fontWeight: 'bold',
        },
      }}
    >
      <IconButton
        onClick={handleCopy}
        sx={{
          position: 'absolute',
          right: 8,
          top: 8,
          color: 'grey.300',
          '&:hover': {
            bgcolor: 'rgba(255, 255, 255, 0.1)',
          },
        }}
        size="small"
        aria-label="Copy code"
      >
        <ContentCopyIcon fontSize="small" />
      </IconButton>

      <div className="code-wrapper">
        {isClient ? (
          <pre className="language-python" tabIndex={0}>
            <code ref={codeRef} className="language-python">
              {code}
            </code>
          </pre>
        ) : (
          <pre
            style={{
              color: theme.palette.mode === 'dark' ? '#d4d4d4' : '#424242',
            }}
          >
            <code>{code}</code>
          </pre>
        )}
      </div>

      <Snackbar
        open={showCopyNotification}
        autoHideDuration={2000}
        onClose={() => setShowCopyNotification(false)}
        message="Code copied to clipboard"
      />
    </Paper>
  );
}
