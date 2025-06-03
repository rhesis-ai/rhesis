'use client';

import { useEffect, useRef, useState } from 'react';
import Prism from 'prismjs';
import 'prismjs/themes/prism-tomorrow.css';
import 'prismjs/components/prism-python';
// Additional Prism components for better Python highlighting
import 'prismjs/plugins/line-numbers/prism-line-numbers.css';
import 'prismjs/plugins/line-numbers/prism-line-numbers.js';
import { Paper, IconButton, Snackbar } from '@mui/material';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';

export default function CodeBlock({ identifier }: { identifier: string }) {
  const [showCopyNotification, setShowCopyNotification] = useState(false);
  const codeRef = useRef<HTMLElement>(null);
  const [isClient, setIsClient] = useState(false);

  const code = `from rhesis.entities import TestSet

# Initialize and load the test set
test_set = TestSet(id="${identifier}")
df = test_set.load()  # Returns a pandas DataFrame

# Alternatively, you can download the CSV file directly
test_set = TestSet(id="${identifier}")
test_set.download()  # Downloads to current directory as test_set_{id}.csv`;

  useEffect(() => {
    setIsClient(true);
    
    // Ensure Prism is available in the browser environment
    if (typeof window !== 'undefined') {
      // Need to re-require Prism here to make sure it's loaded on the client side
      require('prismjs');
      require('prismjs/components/prism-python');
      
      // Force highlighting after the component is mounted
      if (codeRef.current) {
        Prism.highlightElement(codeRef.current);
      }
    }
  }, []);

  // Manually apply highlighting when the component is mounted
  useEffect(() => {
    if (isClient && codeRef.current) {
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
        bgcolor: '#1e1e1e',  // Darker background for better contrast
        position: 'relative',
        borderRadius: '4px',
        '& pre, & code, & span': {
          margin: '0 !important',
          fontSize: '14px !important',  // Slightly larger font
          lineHeight: '1.5 !important',  // Better line height for readability
          fontFamily: '"Roboto Mono", "Fira Code", monospace !important',
        },
        '& pre': {
          backgroundColor: 'transparent !important',
          padding: '8px 0',
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
          color: '#6A9955 !important' 
        },
        '& .token.string': { 
          color: '#ce9178 !important' 
        },
        '& .token.keyword': { 
          color: '#569cd6 !important',
          fontWeight: '500 !important'
        },
        '& .token.function': { 
          color: '#dcdcaa !important' 
        },
        '& .token.class-name': { 
          color: '#4EC9B0 !important' 
        },
        '& .token.operator': { 
          color: '#d4d4d4 !important' 
        },
        '& .token.number': { 
          color: '#b5cea8 !important' 
        },
        '& .token.punctuation': { 
          color: '#d4d4d4 !important' 
        },
        '& .token.builtin': { 
          color: '#4EC9B0 !important' 
        },
        '& .token.important': { 
          color: '#ff9d00 !important',
          fontWeight: 'bold'
        }
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
            <code ref={codeRef} className="language-python">{code}</code>
          </pre>
        ) : (
          <pre style={{ color: '#d4d4d4' }}>
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